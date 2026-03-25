#!/usr/bin/env python3
import json
import os
import re
import subprocess
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/workspace"))
WORKSPACES_DIR = Path(os.environ.get("WORKSPACES_DIR", str(WORKSPACE_DIR / "workspaces")))
STATE_DIR = Path(os.environ.get("STATE_DIR", str(WORKSPACE_DIR / ".state")))
TMUX_SESSION_PREFIX = os.environ.get("TMUX_SESSION_PREFIX", "ws")
RECENT_FILE = STATE_DIR / "recent_workspace"
SELECTED_FILE = STATE_DIR / "selected_workspace"
INVALID_NAMES = {".", ".."}
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

        else:
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return


def main() -> None:
    ensure_base_layout()
    server = ThreadingHTTPServer(("0.0.0.0", 8081), WorkspaceHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
