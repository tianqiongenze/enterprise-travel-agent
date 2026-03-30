#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"

if ! command -v docker >/dev/null 2>&1; then
  printf 'docker is required for rollback_release.sh\n'
  exit 1
fi

(
  cd "$DEPLOY_DIR"
  docker compose down
)

printf 'rollback completed (services stopped)\n'
