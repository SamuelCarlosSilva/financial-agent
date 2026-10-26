#!/usr/bin/env bash
# Smoke test do proxy Nginx da imagem `web` (specs/002-web-chat-frontend/contracts/proxy.md).
#
# Sobe a imagem com um upstream falso (scripts/echo_upstream.py, que devolve o que recebeu) e
# confere rotas, injeção da chave, cabeçalhos de segurança, cache e a re-resolução do nome da
# API (COR-06). Uso:
#   docker build -t finagent-web:smoke frontend && scripts/proxy-smoke.sh finagent-web:smoke
set -euo pipefail

IMAGE=${1:?uso: scripts/proxy-smoke.sh <imagem do web>}
NET=finagent-smoke
PORT=${SMOKE_PORT:-18080}
BASE="http://localhost:${PORT}"
KEY=smoke-key
SCRIPTS=$(cd "$(dirname "$0")" && pwd)
NOT_FOUND='{"error":{"code":"not_found","message":"Rota não encontrada."}}'
TMP=$(mktemp -d)
CHECKS=0

cleanup() {
  docker rm -f smoke-web smoke-api smoke-filler >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

fail() {
  echo "FALHOU: $1" >&2
  echo "  esperado: $2" >&2
  echo "  obtido:   $3" >&2
  exit 1
}

expect_eq() { # descrição, esperado, obtido
  CHECKS=$((CHECKS + 1))
  [[ "$2" == "$3" ]] || fail "$1" "$2" "$3"
}

expect_contains() { # descrição, trecho, texto
  CHECKS=$((CHECKS + 1))
  [[ "$3" == *"$2"* ]] || fail "$1" "contém '$2'" "$3"
}

expect_absent() { # descrição, trecho, texto
  CHECKS=$((CHECKS + 1))
  [[ "$3" != *"$2"* ]] || fail "$1" "sem '$2'" "$3"
}

# get <arquivo-base> <curl args...>: grava status, cabeçalhos (minúsculos) e corpo.
get() {
  local out=$1
  shift
  curl -s -o "$TMP/$out.body" -D "$TMP/$out.raw" -w '%{http_code}' "$@" >"$TMP/$out.status"
  tr '[:upper:]' '[:lower:]' <"$TMP/$out.raw" | tr -d '\r' >"$TMP/$out.headers"
}
status() { cat "$TMP/$1.status"; }
headers() { cat "$TMP/$1.headers"; }
body() { cat "$TMP/$1.body"; }
echoed() { jq -r "$2" "$TMP/$1.body"; }

security_headers() { # arquivo-base
  local h
  h=$(headers "$1")
  expect_contains "$1: CSP" "content-security-policy: default-src 'self'" "$h"
  expect_contains "$1: CSP frame-ancestors" "frame-ancestors 'none'" "$h"
  expect_contains "$1: nosniff" "x-content-type-options: nosniff" "$h"
  expect_contains "$1: referrer" "referrer-policy: no-referrer" "$h"
}

start_echo() {
  docker run -d --name smoke-api --network "$NET" --network-alias api \
    -v "$SCRIPTS/echo_upstream.py:/echo.py:ro" python:3.12-alpine python /echo.py >/dev/null
}

wait_health() {
  for _ in $(seq 1 30); do
    [[ $(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/health") == 200 ]] && return 0
    sleep 1
  done
  return 1
}

docker pull -q python:3.12-alpine >/dev/null
docker network create "$NET" >/dev/null
start_echo
docker run -d --name smoke-web --network "$NET" -p "127.0.0.1:${PORT}:8080" \
  -e API_UPSTREAM=http://api:8000 -e FINAGENT_API_KEY="$KEY" "$IMAGE" >/dev/null
wait_health || fail "subida" "/api/health 200 em até 30 s" "$(docker logs smoke-web 2>&1 | tail -5)"

# 1. Saúde: sem chave para o upstream, mesmo que o cliente mande uma.
get health -H 'X-API-Key: evil' "$BASE/api/health"
expect_eq "health: status" 200 "$(status health)"
expect_eq "health: caminho no upstream" /health "$(echoed health .path)"
expect_eq "health: sem chave no upstream" null "$(echoed health '.headers["x-api-key"]')"
security_headers health

# 2. API: chave do proxy (a do cliente é descartada), query e X-Request-ID repassados.
get thread -H 'X-API-Key: evil' -H 'X-Request-ID: smoke-1' "$BASE/api/v1/threads/abc/messages?x=1"
expect_eq "v1: status" 200 "$(status thread)"
expect_eq "v1: caminho no upstream" /v1/threads/abc/messages "$(echoed thread .path)"
expect_eq "v1: query" x=1 "$(echoed thread .query)"
expect_eq "v1: chave do proxy" "$KEY" "$(echoed thread '.headers["x-api-key"]')"
expect_eq "v1: X-Request-ID" smoke-1 "$(echoed thread '.headers["x-request-id"]')"
expect_absent "v1: chave nunca volta ao cliente" "x-api-key" "$(headers thread)"

# 3. POST chega como POST.
get chat -X POST -H 'Content-Type: application/json' -d '{"message":"oi"}' "$BASE/api/v1/chat"
expect_eq "chat: método" POST "$(echoed chat .method)"
expect_eq "chat: caminho" /v1/chat "$(echoed chat .path)"

# 4. Qualquer outro /api/* é 404 do próprio proxy.
get docs "$BASE/api/docs"
expect_eq "docs: status" 404 "$(status docs)"
expect_eq "docs: corpo" "$NOT_FOUND" "$(body docs)"
security_headers docs

# 5. HTML e fallback de SPA sem cache.
get index "$BASE/"
expect_eq "index: status" 200 "$(status index)"
expect_contains "index: no-cache" "cache-control: no-cache" "$(headers index)"
security_headers index
get spa "$BASE/t/qualquer"
expect_eq "spa: status" 200 "$(status spa)"
expect_contains "spa: devolve o index" '<div id="root">' "$(body spa)"

# 6. Assets com cache longo.
asset=$(grep -o '/assets/[^"]*\.js' "$TMP/index.body" | head -1)
get asset "$BASE$asset"
expect_eq "asset: status" 200 "$(status asset)"
expect_contains "asset: immutable" "cache-control: public, max-age=31536000, immutable" "$(headers asset)"
security_headers asset

# 7. COR-06: a API volta com outro IP e o proxy a encontra sem reiniciar o web.
old_ip=$(docker inspect -f "{{(index .NetworkSettings.Networks \"$NET\").IPAddress}}" smoke-api)
docker rm -f smoke-api >/dev/null
docker run -d --name smoke-filler --network "$NET" python:3.12-alpine sleep 120 >/dev/null
start_echo
new_ip=$(docker inspect -f "{{(index .NetworkSettings.Networks \"$NET\").IPAddress}}" smoke-api)
CHECKS=$((CHECKS + 1))
[[ "$old_ip" != "$new_ip" ]] || fail "COR-06: IP novo" "diferente de $old_ip" "$new_ip"
sleep 11
get reresolve "$BASE/api/health"
expect_eq "COR-06: health depois do IP novo" 200 "$(status reresolve)"

echo "proxy smoke: $CHECKS checagens ok"
