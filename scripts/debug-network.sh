#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_ARGS=(-f docker-compose.yml)
if [ -f docker-compose.proxy.yml ]; then
  COMPOSE_ARGS+=(-f docker-compose.proxy.yml)
fi

pick_compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    printf 'docker compose'
    return 0
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    printf 'docker-compose'
    return 0
  fi

  echo "Cannot find Docker Compose. Install docker compose plugin or docker-compose." >&2
  exit 1
}

COMPOSE_CMD="$(pick_compose_cmd)"

show_header() {
  printf '\n== %s ==\n' "$1"
}

show_header "Host Proxy Env"
env | grep -Ei '^(http|https|all|no)_proxy=' | sort || echo "No proxy env found"

show_header "Host Ports"
ss -lntp | grep -E ':(17890|17891|19090|7890|7891|9090)\b' || echo "No matching ports listening"

show_header "Compose Services"
${COMPOSE_CMD} "${COMPOSE_ARGS[@]}" ps || true

show_header "Mihomo Logs"
${COMPOSE_CMD} "${COMPOSE_ARGS[@]}" logs --tail=80 mihomo || true

show_header "TTyd Logs"
${COMPOSE_CMD} "${COMPOSE_ARGS[@]}" logs --tail=80 ttyd || true

show_header "Host -> Mihomo"
HTTP_PORT="${MIHOMO_HTTP_PORT:-17890}"
API_PORT="${MIHOMO_API_PORT:-19090}"
curl -I --max-time 12 -x "http://127.0.0.1:${HTTP_PORT}" https://api.openai.com/v1/models || true
printf '\n'
curl -fsS --max-time 5 "http://127.0.0.1:${API_PORT}/version" || true
printf '\n'

show_header "Container Env"
${COMPOSE_CMD} "${COMPOSE_ARGS[@]}" exec ttyd bash -lc 'env | grep -Ei "^(http|https|all|no)_proxy=" | sort || true' || true

show_header "Container -> Mihomo"
${COMPOSE_CMD} "${COMPOSE_ARGS[@]}" exec ttyd bash -lc 'curl -fsS --max-time 5 http://mihomo:9090/version || true' || true
printf '\n'
${COMPOSE_CMD} "${COMPOSE_ARGS[@]}" exec ttyd bash -lc 'curl -fsS --max-time 5 http://mihomo:9090/proxies | jq -r "\"Default=\" + (.proxies.Default.now // \"n/a\"), \"OpenAI=\" + (.proxies.OpenAI.now // \"n/a\")" || true' || true
printf '\n'

show_header "Container -> OpenAI"
${COMPOSE_CMD} "${COMPOSE_ARGS[@]}" exec ttyd bash -lc 'curl -I --max-time 12 https://api.openai.com/v1/models || true' || true
printf '\n'
${COMPOSE_CMD} "${COMPOSE_ARGS[@]}" exec ttyd bash -lc 'curl -I --max-time 12 https://platform.openai.com || true' || true
printf '\n'
${COMPOSE_CMD} "${COMPOSE_ARGS[@]}" exec ttyd bash -lc 'curl -I --max-time 12 https://chatgpt.com || true' || true
