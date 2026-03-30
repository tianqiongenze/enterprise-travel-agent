#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"

required_commands=(python3 npm mvn ffmpeg)
for cmd in "${required_commands[@]}"; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    printf 'missing command: %s\n' "$cmd"
    exit 1
  fi
done

test -f "$ROOT_DIR/platform/deploy/nginx/nginx.conf"
test -f "$ROOT_DIR/docs/go-live-checklist.md"
test -f "$ROOT_DIR/docs/release-runbook.md"

printf 'preflight passed\n'
