#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_EXAMPLE="${ROOT_DIR}/.env.example"
ENV_FILE="${ROOT_DIR}/.env"

SITE_ADDR=""
PASSWORD=""
AUTH_USER="admin"
HTTP_PORT=""
HTTPS_PORT=""
APP_UID="$(id -u)"
APP_GID="$(id -g)"
TZ_VALUE="${TZ:-Asia/Shanghai}"
OPENAI_API_KEY_VALUE=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/init-env.sh --password 'strong-password' [options]

Options:
  --site <addr>         Caddy site address. Examples: :80, codex.example.com
  --password <text>     Basic Auth plaintext password
  --user <name>         Basic Auth username (default: admin)
  --http-port <port>    Host HTTP port
  --https-port <port>   Host HTTPS port
  --uid <uid>           APP_UID written to .env (default: current user id)
  --gid <gid>           APP_GID written to .env (default: current group id)
  --tz <timezone>       TZ written to .env (default: Asia/Shanghai or current TZ)
  --api-key <key>       Optional OPENAI_API_KEY
  --env-file <path>     Write to a different env file
  -h, --help            Show this help

Examples:
  ./scripts/init-env.sh --site codex.example.com --password 'change-me'
  ./scripts/init-env.sh --site :80 --http-port 8080 --https-port 8443 --password 'change-me'
  CADDY_IMAGE=docker.m.daocloud.io/library/caddy:2 ./scripts/init-env.sh --site :80 --http-port 80 --password 'change-me'
EOF
}

set_env_var() {
  local key="$1"
  local value="$2"
  local file="$3"
  local tmp_file

  tmp_file="$(mktemp)"
  awk -v key="${key}" -v value="${value}" '
    BEGIN { updated = 0 }
    $0 ~ ("^" key "=") {
      print key "=" value
      updated = 1
      next
    }
    { print }
    END {
      if (!updated) {
        print key "=" value
      }
    }
  ' "${file}" > "${tmp_file}"
  mv "${tmp_file}" "${file}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --site)
      SITE_ADDR="${2:-}"
      shift 2
      ;;
    --password)
      PASSWORD="${2:-}"
      shift 2
      ;;
    --user)
      AUTH_USER="${2:-}"
      shift 2
      ;;
    --http-port)
      HTTP_PORT="${2:-}"
      shift 2
      ;;
    --https-port)
      HTTPS_PORT="${2:-}"
      shift 2
      ;;
    --uid)
      APP_UID="${2:-}"
      shift 2
      ;;
    --gid)
      APP_GID="${2:-}"
      shift 2
      ;;
    --tz)
      TZ_VALUE="${2:-}"
      shift 2
      ;;
    --api-key)
      OPENAI_API_KEY_VALUE="${2:-}"
      shift 2
      ;;
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [ -z "${PASSWORD}" ]; then
  echo "--password is required" >&2
  usage >&2
  exit 1
fi

if [ ! -f "${ENV_EXAMPLE}" ]; then
  echo "Missing template: ${ENV_EXAMPLE}" >&2
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
fi

if [ -z "${SITE_ADDR}" ]; then
  SITE_ADDR=":80"
fi

if [ -z "${HTTP_PORT}" ]; then
  if [[ "${SITE_ADDR}" == :* ]]; then
    HTTP_PORT="8080"
  else
    HTTP_PORT="80"
  fi
fi

if [ -z "${HTTPS_PORT}" ]; then
  if [[ "${SITE_ADDR}" == :* ]]; then
    HTTPS_PORT="8443"
  else
    HTTPS_PORT="443"
  fi
fi

RAW_HASH="$("${ROOT_DIR}/scripts/hash-password.sh" "${PASSWORD}")"
ESCAPED_HASH="$(printf '%s' "${RAW_HASH}" | sed 's/\$/$$/g')"

set_env_var "HTTP_PORT" "${HTTP_PORT}" "${ENV_FILE}"
set_env_var "HTTPS_PORT" "${HTTPS_PORT}" "${ENV_FILE}"
set_env_var "CADDY_SITE_ADDR" "${SITE_ADDR}" "${ENV_FILE}"
set_env_var "BASIC_AUTH_USER" "${AUTH_USER}" "${ENV_FILE}"
set_env_var "BASIC_AUTH_HASH" "${ESCAPED_HASH}" "${ENV_FILE}"
set_env_var "APP_UID" "${APP_UID}" "${ENV_FILE}"
set_env_var "APP_GID" "${APP_GID}" "${ENV_FILE}"
set_env_var "TZ" "${TZ_VALUE}" "${ENV_FILE}"
set_env_var "OPENAI_API_KEY" "${OPENAI_API_KEY_VALUE}" "${ENV_FILE}"

chmod 600 "${ENV_FILE}" || true

cat <<EOF
Wrote ${ENV_FILE}
  CADDY_SITE_ADDR=${SITE_ADDR}
  HTTP_PORT=${HTTP_PORT}
  HTTPS_PORT=${HTTPS_PORT}
  BASIC_AUTH_USER=${AUTH_USER}
  APP_UID=${APP_UID}
  APP_GID=${APP_GID}
  TZ=${TZ_VALUE}

Next:
  docker-compose build ttyd
  docker-compose up -d
EOF
