#!/usr/bin/env bash
set -euo pipefail

SKIP_INSTALL="${SKIP_INSTALL:-false}"
SKIP_K8S="${SKIP_K8S:-false}"
SKIP_LOAD_TEST="${SKIP_LOAD_TEST:-false}"
LOAD_REQUESTS="${LOAD_REQUESTS:-500}"
LOAD_CONCURRENCY="${LOAD_CONCURRENCY:-50}"
PACKAGE_MODE="${PACKAGE_MODE:-${TRAVEL_PACKAGE_MODE:-online}}"
OFFLINE_BUNDLE_DIR="${OFFLINE_BUNDLE_DIR:-${TRAVEL_OFFLINE_BUNDLE_DIR:-platform/deploy/offline_bundle}}"
ARTIFACT_MANIFEST="${ARTIFACT_MANIFEST:-${TRAVEL_ARTIFACT_MANIFEST:-artifacts.manifest.json}}"
OFFLINE_STRICT="${OFFLINE_STRICT:-${TRAVEL_OFFLINE_STRICT:-false}}"
OFFLINE_TOOL_INSTALL_DIR="${OFFLINE_TOOL_INSTALL_DIR:-${TRAVEL_OFFLINE_TOOL_INSTALL_DIR:-var/offline_tools/bin}}"
BUNDLE_SKIP_DOCKER_IMAGES="${BUNDLE_SKIP_DOCKER_IMAGES:-false}"
BUNDLE_SKIP_TOOLS="${BUNDLE_SKIP_TOOLS:-false}"
BUNDLE_TOOL_TARGETS="${BUNDLE_TOOL_TARGETS:-${TRAVEL_BUNDLE_TOOL_TARGETS:-windows-amd64,linux-amd64,darwin-amd64,darwin-arm64}}"
BUNDLE_KUBECTL_VERSION="${BUNDLE_KUBECTL_VERSION:-${TRAVEL_BUNDLE_KUBECTL_VERSION:-v1.31.1}}"
BUNDLE_KIND_VERSION="${BUNDLE_KIND_VERSION:-${TRAVEL_BUNDLE_KIND_VERSION:-v0.29.0}}"
BUNDLE_DOCKER_INSTALLER_WINDOWS="${BUNDLE_DOCKER_INSTALLER_WINDOWS:-${TRAVEL_BUNDLE_DOCKER_INSTALLER_WINDOWS:-}}"
BUNDLE_DOCKER_INSTALLER_LINUX="${BUNDLE_DOCKER_INSTALLER_LINUX:-${TRAVEL_BUNDLE_DOCKER_INSTALLER_LINUX:-}}"
BUNDLE_DOCKER_INSTALLER_MACOS="${BUNDLE_DOCKER_INSTALLER_MACOS:-${TRAVEL_BUNDLE_DOCKER_INSTALLER_MACOS:-}}"
K8S_PROVIDER="${K8S_PROVIDER:-${TRAVEL_K8S_PROVIDER:-kind}}"

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"

cmd=(python3 -u "$ROOT_DIR/platform/deploy/scripts/one_click_stack.py" --project-root "$ROOT_DIR" --load-requests "$LOAD_REQUESTS" --load-concurrency "$LOAD_CONCURRENCY" --package-mode "$PACKAGE_MODE" --offline-bundle-dir "$OFFLINE_BUNDLE_DIR" --artifact-manifest "$ARTIFACT_MANIFEST" --offline-tool-install-dir "$OFFLINE_TOOL_INSTALL_DIR" --bundle-tool-targets "$BUNDLE_TOOL_TARGETS" --bundle-kubectl-version "$BUNDLE_KUBECTL_VERSION" --bundle-kind-version "$BUNDLE_KIND_VERSION" --k8s-provider "$K8S_PROVIDER")
[ "$SKIP_INSTALL" = "true" ] && cmd+=(--skip-install)
[ "$SKIP_K8S" = "true" ] && cmd+=(--skip-k8s)
[ "$SKIP_LOAD_TEST" = "true" ] && cmd+=(--skip-load-test)
[ "$OFFLINE_STRICT" = "true" ] && cmd+=(--offline-strict)
[ "$BUNDLE_SKIP_DOCKER_IMAGES" = "true" ] && cmd+=(--bundle-skip-docker-images)
[ "$BUNDLE_SKIP_TOOLS" = "true" ] && cmd+=(--bundle-skip-tools)
[ -n "$BUNDLE_DOCKER_INSTALLER_WINDOWS" ] && cmd+=(--bundle-docker-installer-windows "$BUNDLE_DOCKER_INSTALLER_WINDOWS")
[ -n "$BUNDLE_DOCKER_INSTALLER_LINUX" ] && cmd+=(--bundle-docker-installer-linux "$BUNDLE_DOCKER_INSTALLER_LINUX")
[ -n "$BUNDLE_DOCKER_INSTALLER_MACOS" ] && cmd+=(--bundle-docker-installer-macos "$BUNDLE_DOCKER_INSTALLER_MACOS")

echo "[run] ${cmd[*]}"
"${cmd[@]}"

