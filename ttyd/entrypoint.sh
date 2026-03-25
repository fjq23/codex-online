#!/usr/bin/env bash
set -euo pipefail

# Map the in-container user to the host UID/GID so mounted files stay writable.
APP_UID="${APP_UID:-1000}"
APP_GID="${APP_GID:-1000}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
WORKSPACES_DIR="${WORKSPACES_DIR:-${WORKSPACE_DIR}/workspaces}"
STATE_DIR="${STATE_DIR:-${WORKSPACE_DIR}/.state}"
CODEX_HOME="${CODEX_HOME:-/codex-home}"
TMUX_SESSION_PREFIX="${TMUX_SESSION_PREFIX:-ws}"

if [ "$(id -u)" -ne 0 ]; then
  echo "entrypoint.sh must start as root" >&2
  exit 1
fi

groupmod -o -g "${APP_GID}" codex
usermod -o -u "${APP_UID}" -g "${APP_GID}" codex

mkdir -p \
  "${WORKSPACES_DIR}" \
  "${STATE_DIR}" \
  "${CODEX_HOME}"

chown -R "${APP_UID}:${APP_GID}" "${WORKSPACE_DIR}" "${CODEX_HOME}" /home/codex

export HOME=/home/codex
export CODEX_HOME
export WORKSPACE_DIR
export WORKSPACES_DIR
export STATE_DIR
export TMUX_SESSION_PREFIX

gosu codex python3 /opt/codex-workbench/api/server.py &
gosu codex bash -lc 'if [ -n "${HTTP_PROXY:-}" ] || [ -n "${ALL_PROXY:-}" ]; then wb proxy-openai-bg 40 --force; fi' >/dev/null 2>&1 &

exec gosu codex ttyd \
  -p 7681 \
  -W \
  -O \
  -b /terminal/session \
  -w "${WORKSPACE_DIR}" \
  -t fontSize=16 \
  -t cursorStyle=bar \
  -t cursorBlink=true \
  bash --login -c "cd '${WORKSPACE_DIR}' && wb attach-selected"
