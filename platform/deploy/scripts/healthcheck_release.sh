#!/usr/bin/env bash
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
RUNTIME_URL="${RUNTIME_URL:-http://localhost:8000}"
WEB_URL="${WEB_URL:-http://localhost:5173}"

curl --fail --silent "$RUNTIME_URL/health" >/dev/null
curl --fail --silent "$GATEWAY_URL/api/v1/travel/health" >/dev/null
curl --fail --silent "$WEB_URL" >/dev/null

printf 'healthcheck passed\n'
