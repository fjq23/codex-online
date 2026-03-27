#!/usr/bin/env bash
set -euo pipefail

# Sync local Codex auth/config to the deployed server and align the server-side
# config with a low-friction "full access" default for interactive Codex usage.

usage() {
  cat <<'EOF'
Usage:
  ./scripts/push-codex-auth.sh <user@host> [--remote-dir DIR] [--source DIR]

Examples:
  ./scripts/push-codex-auth.sh jiaqi@8.147.132.212
  ./scripts/push-codex-auth.sh jiaqi@8.147.132.212 --remote-dir ~/codex-online --source ~/.codex

What it does:
  1. Uploads auth.json and a patched config.toml to the server project
  2. Sets default Codex mode to full access on the server
  3. Restarts the ttyd container so the new auth/config takes effect

Notes:
  - The script will prompt for the server password and, if needed, sudo password.
  - The patched config adds:
      approval_policy = "never"
      sandbox_mode = "danger-full-access"
    and marks /workspace plus /workspace/workspaces as trusted.
EOF
}

TARGET="${1:-}"
shift || true

REMOTE_DIR="\$HOME/codex-online"
SOURCE_DIR="${HOME}/.codex"

while [ $# -gt 0 ]; do
  case "$1" in
    --remote-dir)
      REMOTE_DIR="${2:-}"
      shift 2
      ;;
    --source)
      SOURCE_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [ -z "${TARGET}" ]; then
  usage >&2
  exit 1
fi

AUTH_FILE="${SOURCE_DIR}/auth.json"
CONFIG_FILE="${SOURCE_DIR}/config.toml"

if [ ! -f "${AUTH_FILE}" ]; then
  echo "Missing auth file: ${AUTH_FILE}" >&2
  exit 1
fi

if [ ! -f "${CONFIG_FILE}" ]; then
  echo "Missing config file: ${CONFIG_FILE}" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

cp "${AUTH_FILE}" "${TMP_DIR}/auth.json"

python3 - "${CONFIG_FILE}" "${TMP_DIR}/config.toml" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])

text = src.read_text(encoding="utf-8")
lines = text.splitlines()

desired_top = [
    'approval_policy = "never"',
    'sandbox_mode = "danger-full-access"',
]
managed_tables = {
    '[projects."/workspace"]',
    '[projects."/workspace/workspaces"]',
}

output = []
skip_managed_table = False
inserted_top = False
current_table = None

def emit_top():
    global inserted_top
    if inserted_top:
        return
    output.extend(desired_top)
    output.append("")
    inserted_top = True

for line in lines:
    stripped = line.strip()
    is_table = stripped.startswith("[") and stripped.endswith("]")

    if is_table:
      if stripped in managed_tables:
        skip_managed_table = True
        current_table = stripped
        continue
      skip_managed_table = False
      current_table = stripped
      emit_top()
      output.append(line)
      continue

    if skip_managed_table:
      continue

    if current_table is None:
      if stripped.startswith("approval_policy") or stripped.startswith("sandbox_mode"):
        continue

    output.append(line)

if not inserted_top:
    emit_top()

content = "\n".join(output).rstrip() + "\n\n"
content += '[projects."/workspace"]\ntrust_level = "trusted"\n\n'
content += '[projects."/workspace/workspaces"]\ntrust_level = "trusted"\n'

dst.write_text(content, encoding="utf-8")
PY

echo "Preparing remote codex-home directory on ${TARGET} ..."
ssh -t "${TARGET}" "REMOTE_DIR=${REMOTE_DIR}; cd \"\${REMOTE_DIR}\" && sudo mkdir -p data/codex-home && sudo chown -R \$(id -un):\$(id -gn) data/codex-home && chmod 700 data/codex-home"

echo "Uploading auth.json and config.toml ..."
scp "${TMP_DIR}/auth.json" "${TMP_DIR}/config.toml" "${TARGET}:codex-online/data/codex-home/"

echo "Fixing permissions and restarting ttyd ..."
ssh -t "${TARGET}" "REMOTE_DIR=${REMOTE_DIR}; cd \"\${REMOTE_DIR}\" && chmod 600 data/codex-home/auth.json data/codex-home/config.toml && sudo docker compose restart ttyd && sudo docker compose exec ttyd bash -lc 'codex login status && printf \"\\n== /codex-home/config.toml ==\\n\" && sed -n \"1,40p\" /codex-home/config.toml'"

echo
echo "Done."
echo "Server auth has been refreshed, and default Codex mode is now full access."
