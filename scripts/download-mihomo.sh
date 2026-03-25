#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${ROOT_DIR}/proxy/mihomo/bin"
TARGET_FILE="${TARGET_DIR}/mihomo"
RELEASE_API="https://api.github.com/repos/MetaCubeX/mihomo/releases"
VERSION="${1:-latest}"

detect_asset_name() {
  local arch
  arch="$(uname -m)"

  case "${arch}" in
    x86_64|amd64)
      printf '%s\n' "mihomo-linux-amd64-compatible"
      ;;
    aarch64|arm64)
      printf '%s\n' "mihomo-linux-arm64"
      ;;
    *)
      echo "Unsupported architecture: ${arch}" >&2
      exit 1
      ;;
  esac
}

resolve_download_url() {
  local version="$1"
  local asset_prefix="$2"

  python3 - "$version" "$asset_prefix" "$RELEASE_API" <<'PY'
import json
import sys
import urllib.request

version = sys.argv[1]
asset_prefix = sys.argv[2]
release_api = sys.argv[3]

if version == "latest":
    url = f"{release_api}/latest"
else:
    url = f"{release_api}/tags/{version}"

with urllib.request.urlopen(url) as response:
    release = json.load(response)

for asset in release.get("assets", []):
    name = asset.get("name", "")
    if name.startswith(asset_prefix) and name.endswith(".gz"):
        print(asset["browser_download_url"])
        raise SystemExit(0)

raise SystemExit(f"Could not find asset for prefix: {asset_prefix}")
PY
}

mkdir -p "${TARGET_DIR}"

ASSET_PREFIX="$(detect_asset_name)"
DOWNLOAD_URL="$(resolve_download_url "${VERSION}" "${ASSET_PREFIX}")"
TMP_GZ="$(mktemp /tmp/mihomo.XXXXXX.gz)"

echo "Downloading ${DOWNLOAD_URL}"
curl -fL "${DOWNLOAD_URL}" -o "${TMP_GZ}"
gzip -dc "${TMP_GZ}" > "${TARGET_FILE}"
chmod 0755 "${TARGET_FILE}"
rm -f "${TMP_GZ}"

echo "Saved to ${TARGET_FILE}"
file "${TARGET_FILE}" || true
