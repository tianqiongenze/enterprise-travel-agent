#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"

KUSTOMIZE_OVERLAY="${KUSTOMIZE_OVERLAY:-}"

if ! command -v docker >/dev/null 2>&1; then
  printf 'docker is required for deploy_release.sh\n'
  if [ -z "$KUSTOMIZE_OVERLAY" ]; then
    exit 1
  fi
fi

if [ -n "$KUSTOMIZE_OVERLAY" ]; then
  if ! command -v kubectl >/dev/null 2>&1; then
    printf 'kubectl is required when KUSTOMIZE_OVERLAY is set\n'
    exit 1
  fi
  kubectl apply -k "$ROOT_DIR/deploy/k8s/kustomize/overlays/$KUSTOMIZE_OVERLAY"
  printf 'kustomize deploy completed for overlay=%s\n' "$KUSTOMIZE_OVERLAY"
  exit 0
fi

(
  cd "$DEPLOY_DIR"
  docker compose up -d
)

printf 'deploy completed\n'
