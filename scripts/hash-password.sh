#!/usr/bin/env bash
set -euo pipefail

# Generate a Caddy-compatible bcrypt hash for BASIC_AUTH_HASH.
if [ $# -ne 1 ]; then
  echo "Usage: ./scripts/hash-password.sh <plaintext-password>" >&2
  exit 1
fi

exec docker run --rm caddy:2 caddy hash-password --plaintext "$1"

