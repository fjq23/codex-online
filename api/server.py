#!/usr/bin/env python3
import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/workspace"))
WORKSPACES_DIR = Path(os.environ.get("WORKSPACES_DIR", str(WORKSPACE_DIR / "workspaces")))
STATE_DIR = Path(os.environ.get("STATE_DIR", str(WORKSPACE_DIR / ".state")))
RECENT_FILE = STATE_DIR / "recent_workspace"
SELECTED_FILE = STATE_DIR / "selected_workspace"
INVALID_NAMES = {".", ".."}


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
        if path != "/api/workspaces/open":
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        ensure_base_layout()
        payload = self.read_json()
        name = resolve_workspace_name(str(payload.get("name", "")))
        if not name:
            self.send_json({"error": "Workspace name is required."}, HTTPStatus.BAD_REQUEST)
            return

        ensure_workspace_dir(name)
        write_state(name)
        self.send_json({"name": name})


def main() -> None:
    ensure_base_layout()
    server = ThreadingHTTPServer(("0.0.0.0", 8081), WorkspaceHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
