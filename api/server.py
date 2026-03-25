#!/usr/bin/env python3
import json
import os
import re
import subprocess
import hashlib
import shutil
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/workspace"))
WORKSPACES_DIR = Path(os.environ.get("WORKSPACES_DIR", str(WORKSPACE_DIR / "workspaces")))
STATE_DIR = Path(os.environ.get("STATE_DIR", str(WORKSPACE_DIR / ".state")))
TMUX_SESSION_PREFIX = os.environ.get("TMUX_SESSION_PREFIX", "ws")
HTTP_PROXY = os.environ.get("HTTP_PROXY", "")
HTTPS_PROXY = os.environ.get("HTTPS_PROXY", "")
ALL_PROXY = os.environ.get("ALL_PROXY", "")
MIHOMO_CONTROLLER_URL = os.environ.get("MIHOMO_CONTROLLER_URL", "http://mihomo:9090")
RECENT_FILE = STATE_DIR / "recent_workspace"
SELECTED_FILE = STATE_DIR / "selected_workspace"
INVALID_NAMES = {".", ".."}
CPU_SNAPSHOT: tuple[int, int] | None = None
AUTO_RECOVERY_COOLDOWN_SECONDS = int(os.environ.get("AUTO_RECOVERY_COOLDOWN_SECONDS", "90"))
RECOVERY_TRIGGER_FILE = STATE_DIR / "proxy-recovery-last-trigger"
SPECIAL_KEYS = {
    "Enter",
    "Escape",
    "Tab",
    "Space",
    "Up",
    "Down",
    "Left",
    "Right",
    "BSpace",
    "Delete",
    "C-c",
    "C-d",
    "C-a",
    "C-e",
    "C-l",
    "C-u",
    "C-w",
    "C-z",
}


def ensure_base_layout() -> None:
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def read_state(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def write_state(name: str) -> None:
    RECENT_FILE.write_text(name + "\n", encoding="utf-8")
    SELECTED_FILE.write_text(name + "\n", encoding="utf-8")


def slugify(raw: str) -> str:
    lowered = raw.strip().lower()
    lowered = re.sub(r"[^a-z0-9._-]+", "-", lowered)
    return lowered.strip("-")


def sanitize_unicode_name(raw: str) -> str:
    cleaned = re.sub(r"\s+", "-", raw.strip())
    cleaned = re.sub(r"[\x00-\x1f\x7f/\\]+", "-", cleaned)
    cleaned = cleaned.strip(" .-")
    if not cleaned or cleaned in INVALID_NAMES or cleaned.startswith("."):
        return ""
    return cleaned


def resolve_workspace_name(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""

    if (WORKSPACES_DIR / raw).is_dir():
        return raw

    ascii_name = slugify(raw)
    if ascii_name and ascii_name not in INVALID_NAMES and not ascii_name.startswith("."):
        return ascii_name

    return sanitize_unicode_name(raw)


def ensure_workspace_dir(name: str) -> None:
    workspace_dir = WORKSPACES_DIR / name
    workspace_dir.mkdir(parents=True, exist_ok=True)


def session_name_for(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "workspace"
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
    return f"{TMUX_SESSION_PREFIX}_{safe}_{digest}"


def current_workspace_name(explicit: str = "") -> str:
    if explicit:
        resolved = resolve_workspace_name(explicit)
        if resolved and (WORKSPACES_DIR / resolved).is_dir():
            return resolved

    for path in (SELECTED_FILE, RECENT_FILE):
        name = read_state(path)
        if name and (WORKSPACES_DIR / name).is_dir():
            return name
    return ""


def current_pane_for_workspace(name: str) -> str:
    session = session_name_for(name)

    exists = subprocess.run(
        ["tmux", "has-session", "-t", session],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if exists.returncode != 0:
        return ""

    for command in (
        ["tmux", "display-message", "-p", "-t", session, "#{pane_id}"],
        ["tmux", "list-panes", "-t", session, "-F", "#{pane_id}"],
    ):
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        pane = result.stdout.strip().splitlines()
        if pane:
            return pane[0]

    return ""


def send_tmux_action(pane: str, mode: str, value: str) -> None:
    if mode == "literal":
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, "-l", value],
            check=True,
            capture_output=True,
            text=True,
        )
        return

    subprocess.run(
        ["tmux", "send-keys", "-t", pane, value],
        check=True,
        capture_output=True,
        text=True,
    )


def pane_in_mode(pane: str) -> bool:
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", pane, "#{pane_in_mode}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() == "1"


def send_tmux_scroll_action(pane: str, action: str) -> None:
    if action == "page-up":
        subprocess.run(["tmux", "copy-mode", "-t", pane], check=True, capture_output=True, text=True)
        subprocess.run(["tmux", "send-keys", "-t", pane, "-X", "page-up"], check=True, capture_output=True, text=True)
        return

    if action == "page-down":
        subprocess.run(["tmux", "copy-mode", "-t", pane], check=True, capture_output=True, text=True)
        subprocess.run(["tmux", "send-keys", "-t", pane, "-X", "page-down"], check=True, capture_output=True, text=True)
        return

    if action == "top":
        subprocess.run(["tmux", "copy-mode", "-t", pane], check=True, capture_output=True, text=True)
        subprocess.run(["tmux", "send-keys", "-t", pane, "-X", "start-of-history"], check=True, capture_output=True, text=True)
        return

    if action in {"bottom", "live"}:
        if pane_in_mode(pane):
            subprocess.run(["tmux", "send-keys", "-t", pane, "-X", "cancel"], check=True, capture_output=True, text=True)
        return

    raise ValueError(f"Unsupported tmux action: {action}")


def normalize_sequence(payload: dict) -> list[dict[str, str]]:
    if isinstance(payload.get("sequence"), list):
        raw_items = payload["sequence"]
    else:
        raw_items = [{"mode": payload.get("mode", "literal"), "value": payload.get("value", "")}]

    sequence: list[dict[str, str]] = []
    for item in raw_items[:6]:
        if not isinstance(item, dict):
            continue

        mode = str(item.get("mode", "literal")).strip().lower()
        value = str(item.get("value", ""))
        if mode not in {"literal", "special"} or not value:
            continue

        if mode == "literal":
            if len(value) > 4096:
                raise ValueError("Literal input is too long.")
        else:
            if value not in SPECIAL_KEYS:
                raise ValueError(f"Unsupported special key: {value}")

        sequence.append({"mode": mode, "value": value})

    if not sequence:
        raise ValueError("Key input is required.")

    return sequence


def list_workspaces() -> list[str]:
    ensure_base_layout()
    return sorted(path.name for path in WORKSPACES_DIR.iterdir() if path.is_dir())


def read_cpu_times() -> tuple[int, int]:
    with open("/proc/stat", "r", encoding="utf-8") as handle:
        parts = handle.readline().split()
    values = [int(item) for item in parts[1:]]
    idle = values[3] + values[4]
    total = sum(values)
    return total, idle


def cpu_percent() -> float:
    global CPU_SNAPSHOT
    total, idle = read_cpu_times()
    if CPU_SNAPSHOT is None:
      CPU_SNAPSHOT = (total, idle)
      return 0.0

    prev_total, prev_idle = CPU_SNAPSHOT
    CPU_SNAPSHOT = (total, idle)
    total_delta = total - prev_total
    idle_delta = idle - prev_idle
    if total_delta <= 0:
        return 0.0
    return round(max(0.0, min(100.0, 100.0 * (1.0 - (idle_delta / total_delta)))), 1)


def memory_status() -> dict:
    values: dict[str, int] = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as handle:
        for line in handle:
            key, raw_value = line.split(":", 1)
            values[key] = int(raw_value.strip().split()[0]) * 1024

    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    used = max(0, total - available)
    percent = round((used / total) * 100, 1) if total else 0.0
    gib = 1024 ** 3
    return {
        "percent": percent,
        "used_gb": round(used / gib, 1),
        "total_gb": round(total / gib, 1),
    }


def disk_status() -> dict:
    usage = shutil.disk_usage(str(WORKSPACE_DIR if WORKSPACE_DIR.exists() else Path("/")))
    percent = round((usage.used / usage.total) * 100, 1) if usage.total else 0.0
    gib = 1024 ** 3
    return {
        "percent": percent,
        "used_gb": round(usage.used / gib, 1),
        "total_gb": round(usage.total / gib, 1),
    }


def uptime_hours() -> float:
    with open("/proc/uptime", "r", encoding="utf-8") as handle:
        seconds = float(handle.read().split()[0])
    return round(seconds / 3600.0, 1)


def system_status_payload() -> dict:
    load1, load5, load15 = os.getloadavg()
    return {
        "cpu_percent": cpu_percent(),
        "memory": memory_status(),
        "disk": disk_status(),
        "load": {
            "one": round(load1, 2),
            "five": round(load5, 2),
            "fifteen": round(load15, 2),
        },
        "uptime_hours": uptime_hours(),
        "timestamp": int(time.time()),
    }


def read_openai_probe_state() -> dict[str, str]:
    state_file = STATE_DIR / "openai-proxy-probe.state"
    if not state_file.exists():
        return {"status": "idle", "detail": ""}

    parts = state_file.read_text(encoding="utf-8").strip().split("\t", 2)
    return {
        "timestamp": parts[0] if len(parts) > 0 else "",
        "status": parts[1] if len(parts) > 1 else "idle",
        "detail": parts[2] if len(parts) > 2 else "",
    }


def maybe_trigger_proxy_recovery(force: bool = False) -> None:
    if not any((HTTP_PROXY, HTTPS_PROXY, ALL_PROXY)):
        return

    now = int(time.time())
    last_trigger = 0
    if RECOVERY_TRIGGER_FILE.exists():
        try:
            last_trigger = int(RECOVERY_TRIGGER_FILE.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            last_trigger = 0

    if not force and now - last_trigger < AUTO_RECOVERY_COOLDOWN_SECONDS:
        return

    RECOVERY_TRIGGER_FILE.write_text(f"{now}\n", encoding="utf-8")
    subprocess.Popen(
        [
            "bash",
            "-lc",
            "PATH=$PATH:/opt/codex-workbench/bin wb proxy-openai-bg 40 --force >/dev/null 2>&1",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def fetch_mihomo_proxies() -> dict:
    with urlopen(f"{MIHOMO_CONTROLLER_URL}/proxies", timeout=2.5) as response:
        return json.loads(response.read().decode("utf-8"))


def codex_login_mode() -> str:
    result = subprocess.run(
        ["codex", "login", "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or result.stderr).strip()
    if "ChatGPT" in output:
        return "chatgpt"
    if "API key" in output:
        return "api_key"
    if "Not logged in" in output:
        return "logged_out"
    return "unknown"


def probe_url_status(url: str, timeout: float = 4.0, reject_cf_challenge: bool = False) -> tuple[bool, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "codex-mobile-workbench/1.0",
            "Accept": "*/*",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if reject_cf_challenge and response.headers.get("cf-mitigated", "").lower() == "challenge":
                return False, "cf-challenge"
            return True, str(response.getcode())
    except HTTPError as error:
        if reject_cf_challenge and error.headers.get("cf-mitigated", "").lower() == "challenge":
            return False, "cf-challenge"
        if error.code in {200, 204, 301, 302, 307, 308, 401, 403, 405}:
            return True, str(error.code)
        return False, f"http-{error.code}"
    except URLError as error:
        return False, str(error.reason)
    except TimeoutError:
        return False, "timeout"
    except Exception as error:  # pragma: no cover - defensive
        return False, str(error)


def codex_network_payload() -> dict:
    login_mode = codex_login_mode()
    api_ok, api_detail = probe_url_status("https://api.openai.com/v1/models")

    if login_mode == "logged_out":
        return {
            "ready": False,
            "label": "Login required",
            "detail": "Codex is not logged in yet.",
            "mode": login_mode,
        }

    if api_ok:
        return {
            "ready": True,
            "label": "Proxy ready",
            "detail": f"api.openai.com={api_detail}",
            "mode": login_mode,
        }

    return {
        "ready": False,
        "label": "Codex blocked",
        "detail": f"api.openai.com={api_detail}",
        "mode": login_mode,
    }


def proxy_status_payload() -> dict:
    configured = any((HTTP_PROXY, HTTPS_PROXY, ALL_PROXY))
    if not configured:
        return {
            "configured": False,
            "ready": True,
            "label": "Direct mode",
            "detail": "No outbound proxy configured.",
        }

    probe_state = read_openai_probe_state()
    network = codex_network_payload()
    try:
        proxies = fetch_mihomo_proxies().get("proxies", {})
        current = (proxies.get("OpenAI") or {}).get("now", "")
        ready = probe_state.get("status") == "ok" and network.get("ready", False)
        detail_parts = []
        if current:
            detail_parts.append(current)
        if network.get("detail"):
            detail_parts.append(network["detail"])
        detail = " | ".join(detail_parts)
        if ready:
            return {
                "configured": True,
                "ready": True,
                "label": network.get("label", "Proxy ready"),
                "detail": detail,
            }
        state_status = probe_state.get("status", "")
        state_file = STATE_DIR / "openai-proxy-probe.state"
        try:
            state_age = max(0, int(time.time() - state_file.stat().st_mtime))
        except FileNotFoundError:
            state_age = AUTO_RECOVERY_COOLDOWN_SECONDS

        if state_status != "running":
            if state_status == "ok" or state_age >= AUTO_RECOVERY_COOLDOWN_SECONDS or not state_status:
                maybe_trigger_proxy_recovery(force=True)
        return {
            "configured": True,
            "ready": False,
            "label": network.get("label", "Proxy warming"),
            "detail": detail or current or probe_state.get("detail", "") or "OpenAI route is still probing.",
        }
    except (URLError, TimeoutError, json.JSONDecodeError):
        return {
            "configured": True,
            "ready": False,
            "label": "Proxy offline",
            "detail": "Cannot reach the Mihomo controller.",
        }


class WorkspaceHandler(BaseHTTPRequestHandler):
    server_version = "workspace-api/1.0"

    def log_message(self, format: str, *args) -> None:
        return

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/workspaces":
          self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
          return

        ensure_base_layout()
        self.send_json(
            {
                "workspaces": list_workspaces(),
                "recent": read_state(RECENT_FILE),
                "selected": read_state(SELECTED_FILE),
                "proxy": proxy_status_payload(),
                "system": system_status_payload(),
            }
        )

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/workspaces/open":
            ensure_base_layout()
            payload = self.read_json()
            name = resolve_workspace_name(str(payload.get("name", "")))
            if not name:
                self.send_json({"error": "Workspace name is required."}, HTTPStatus.BAD_REQUEST)
                return

            ensure_workspace_dir(name)
            write_state(name)
            self.send_json({"name": name})
            return

        if path == "/api/terminal/send-key":
            ensure_base_layout()
            payload = self.read_json()
            workspace_name = current_workspace_name(str(payload.get("workspace", "")))
            if not workspace_name:
                self.send_json({"error": "No workspace selected."}, HTTPStatus.CONFLICT)
                return

            pane = current_pane_for_workspace(workspace_name)
            if not pane:
                self.send_json({"error": "The workspace terminal is not attached yet."}, HTTPStatus.CONFLICT)
                return

            try:
                sequence = normalize_sequence(payload)
                for item in sequence:
                    send_tmux_action(pane, item["mode"], item["value"])
            except ValueError as error:
                self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            except subprocess.CalledProcessError as error:
                message = error.stderr.strip() or error.stdout.strip() or "Failed to send key."
                self.send_json({"error": message}, HTTPStatus.BAD_GATEWAY)
                return

            self.send_json({"ok": True, "workspace": workspace_name})
            return

        if path == "/api/terminal/tmux-action":
            ensure_base_layout()
            payload = self.read_json()
            workspace_name = current_workspace_name(str(payload.get("workspace", "")))
            if not workspace_name:
                self.send_json({"error": "No workspace selected."}, HTTPStatus.CONFLICT)
                return

            pane = current_pane_for_workspace(workspace_name)
            if not pane:
                self.send_json({"error": "The workspace terminal is not attached yet."}, HTTPStatus.CONFLICT)
                return

            action = str(payload.get("action", "")).strip().lower()
            try:
                send_tmux_scroll_action(pane, action)
            except ValueError as error:
                self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            except subprocess.CalledProcessError as error:
                message = error.stderr.strip() or error.stdout.strip() or "Failed to control tmux."
                self.send_json({"error": message}, HTTPStatus.BAD_GATEWAY)
                return

            self.send_json({"ok": True, "workspace": workspace_name, "action": action})
            return

        else:
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return


def main() -> None:
    ensure_base_layout()
    server = ThreadingHTTPServer(("0.0.0.0", 8081), WorkspaceHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
