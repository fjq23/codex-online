#!/usr/bin/env bash
set -euo pipefail

# Generate a Caddy-compatible bcrypt hash for BASIC_AUTH_HASH.
if [ $# -ne 1 ]; then
  echo "Usage: ./scripts/hash-password.sh <plaintext-password>" >&2
  exit 1
fi

CADDY_IMAGE="${CADDY_IMAGE:-caddy:2}"

pick_docker_cmd() {
  if docker info >/dev/null 2>&1; then
    printf 'docker\n'
    return 0
  fi

  if command -v sudo >/dev/null 2>&1; then
    if sudo -n docker info >/dev/null 2>&1; then
      printf 'sudo docker\n'
      return 0
    fi

    if sudo -v >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
      printf 'sudo docker\n'
      return 0
    fi
  fi

  echo "Cannot access Docker. Run with a user that can use Docker, or configure sudo for Docker." >&2
  exit 1
}

DOCKER_CMD="$(pick_docker_cmd)"

exec ${DOCKER_CMD} run --rm "${CADDY_IMAGE}" caddy hash-password --plaintext "$1"
