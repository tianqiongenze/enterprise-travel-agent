#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"

PYTHONPATH="$ROOT_DIR/services/techgroup-enterprise-travel-runtime" python3 -m unittest discover -s "$ROOT_DIR/tests" -p "test_*.py" -v

(
  cd "$ROOT_DIR/services/techgroup-enterprise-travel-gateway"
  mvn -B test
)

(
  cd "$ROOT_DIR/apps/techgroup-enterprise-travel-web"
  npm install --include=dev
  npm run build
)

if command -v go >/dev/null 2>&1; then
  (
    cd "$ROOT_DIR/services/techgroup-enterprise-travel-ranker-go"
    go mod tidy
    go build ./...
  )
  (
    cd "$ROOT_DIR/services/techgroup-enterprise-travel-policy-go"
    go mod tidy
    go build ./...
  )
  (
    cd "$ROOT_DIR/services/techgroup-enterprise-travel-fanout-go"
    go mod tidy
    go build ./...
  )
  (
    cd "$ROOT_DIR/services/techgroup-enterprise-travel-registry-cache-go"
    go mod tidy
    go build ./...
  )
else
  printf 'go command not found, skip local go build in build_release.sh\n'
fi

printf 'build release completed\n'
