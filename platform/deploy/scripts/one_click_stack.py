"""Cross-platform one-click build/deploy/load-test workflow for local machines."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import hashlib
import stat
import subprocess
import sys
import time
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> int:
    print("[run]", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}")
    return result.returncode


def _which(name: str) -> bool:
    return shutil.which(name) is not None


def _ensure_tool(name: str, skip_install: bool) -> None:
    if _which(name):
        return
    if skip_install:
        raise RuntimeError(f"missing command: {name}")

    system = platform.system().lower()
    if system == "windows":
        install_map = {
            "docker": ["winget", "install", "--id", "Docker.DockerDesktop", "-e"],
            "kubectl": ["winget", "install", "--id", "Kubernetes.kubectl", "-e"],
            "kind": ["winget", "install", "--id", "Kubernetes.kind", "-e"],
        }
    elif system == "darwin":
        install_map = {
            "docker": ["brew", "install", "--cask", "docker"],
            "kubectl": ["brew", "install", "kubectl"],
            "kind": ["brew", "install", "kind"],
        }
    else:
        install_map = {
            "docker": ["bash", "-lc", "curl -fsSL https://get.docker.com | sh"],
            "kubectl": ["bash", "-lc", "sudo apt-get update && sudo apt-get install -y kubectl"],
            "kind": ["bash", "-lc", "go install sigs.k8s.io/kind@v0.29.0"],
        }

    if name not in install_map:
        raise RuntimeError(f"no installer configured for {name}")

    _run(install_map[name])
    if not _which(name):
        raise RuntimeError(f"install finished but command still missing: {name}")


def _str_to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _verify_manifest(bundle_dir: Path, manifest_path: Path, strict: bool) -> dict:
    if not manifest_path.exists():
        raise RuntimeError(f"offline manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    mismatches: list[str] = []
    missing: list[str] = []
    for item in files:
        rel_path = item.get("path")
        expected = item.get("sha256")
        if not rel_path or not expected:
            continue
        full_path = bundle_dir / rel_path
        if not full_path.exists():
            missing.append(rel_path)
            continue
        actual = _sha256_file(full_path)
        if actual != expected:
            mismatches.append(rel_path)

    if missing or mismatches:
        message = (
            f"offline bundle validation failed, missing={missing or '[]'}, "
            f"checksum_mismatch={mismatches or '[]'}"
        )
        if strict:
            raise RuntimeError(message)
        print(f"[warn] {message}")
    else:
        print("[offline] artifact manifest validation passed")
    return manifest


def _load_offline_images(bundle_dir: Path, manifest: dict, strict: bool) -> None:
    images = manifest.get("images", [])
    image_dir = bundle_dir / "images"
    loaded_count = 0

    for item in images:
        archive = item.get("archive")
        if not archive:
            continue
        tar_path = bundle_dir / archive
        if not tar_path.exists():
            msg = f"offline image archive missing: {tar_path}"
            if strict:
                raise RuntimeError(msg)
            print(f"[warn] {msg}")
            continue
        _run(["docker", "load", "-i", str(tar_path)])
        loaded_count += 1

    if loaded_count == 0 and image_dir.exists():
        for tar_path in sorted(image_dir.glob("*.tar")):
            _run(["docker", "load", "-i", str(tar_path)])
            loaded_count += 1

    if loaded_count == 0:
        msg = "no offline docker image archives were loaded"
        if strict:
            raise RuntimeError(msg)
        print(f"[warn] {msg}")
    else:
        print(f"[offline] loaded {loaded_count} docker image archive(s)")


def _current_tool_target() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = "amd64"
    if machine in {"arm64", "aarch64"}:
        arch = "arm64"
    if system == "windows":
        return f"windows-{arch}"
    if system == "darwin":
        return f"darwin-{arch}"
    return f"linux-{arch}"


def _install_offline_tools(bundle_dir: Path, install_dir: Path, strict: bool) -> None:
    target = _current_tool_target()
    source_dir = bundle_dir / "tools" / target
    install_dir.mkdir(parents=True, exist_ok=True)

    if not source_dir.exists():
        msg = f"offline tools not found for target {target}: {source_dir}"
        if strict:
            raise RuntimeError(msg)
        print(f"[warn] {msg}")
        return

    tool_names = ["kubectl.exe", "kind.exe"] if target.startswith("windows") else ["kubectl", "kind"]
    for name in tool_names:
        src = source_dir / name
        if not src.exists():
            msg = f"offline tool missing: {src}"
            if strict:
                raise RuntimeError(msg)
            print(f"[warn] {msg}")
            continue
        dst = install_dir / name
        shutil.copy2(src, dst)
        if not target.startswith("windows"):
            dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"[offline] installed tool: {dst}")

    if not _which("docker") and target.startswith("windows"):
        installer = source_dir / "docker-desktop-installer.exe"
        if installer.exists():
            _run([str(installer), "install", "--quiet", "--accept-license"], check=False)
            print("[offline] attempted Docker Desktop silent install")
        else:
            msg = "docker command missing and no offline docker installer found"
            if strict:
                raise RuntimeError(msg)
            print(f"[warn] {msg}")


def _build_runtime_images(root: Path) -> None:
    docker_dir = root / "platform" / "deploy" / "docker"
    builds = [
        (docker_dir / "Dockerfile.travel-agent-api", "enterprise-travel-agent-api:local"),
        (docker_dir / "Dockerfile.travel-gateway", "enterprise-travel-agent-gateway:local"),
        (docker_dir / "Dockerfile.travel-web", "enterprise-travel-agent-web:local"),
    ]
    for dockerfile, tag in builds:
        if not dockerfile.exists():
            raise RuntimeError(f"dockerfile not found: {dockerfile}")
        _run(["docker", "build", "-f", str(dockerfile), "-t", tag, str(root)])


def _create_fault_sample(path: Path) -> None:
    payload = {
        "scenarios": [
            {"name": "region-a failover", "status": "PASS"},
            {"name": "region-b failover", "status": "PASS"},
            {"name": "cross-region stream recover", "status": "PASS"},
        ],
        "scenarioCount": 3,
        "recoveryRtoMinutes": 10,
        "recoveryRpoSeconds": 30,
        "eventConsumerLagSeconds": 10,
        "eventConsumerDlqTotal": 0,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="One-click local stack workflow")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--skip-k8s", action="store_true")
    parser.add_argument("--skip-load-test", action="store_true")
    parser.add_argument("--load-requests", type=int, default=500)
    parser.add_argument("--load-concurrency", type=int, default=50)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--run-id", default=f"local-{int(time.time())}")
    parser.add_argument("--signing-key-env", default="TRAVEL_EVIDENCE_SIGNING_KEY")
    parser.add_argument(
        "--package-mode",
        choices=["online", "prepare", "offline"],
        default=os.getenv("TRAVEL_PACKAGE_MODE", "online"),
    )
    parser.add_argument(
        "--offline-bundle-dir",
        default=os.getenv("TRAVEL_OFFLINE_BUNDLE_DIR", "platform/deploy/offline_bundle"),
    )
    parser.add_argument(
        "--artifact-manifest",
        default=os.getenv("TRAVEL_ARTIFACT_MANIFEST", "artifacts.manifest.json"),
    )
    parser.add_argument(
        "--offline-strict",
        action="store_true",
        default=_str_to_bool(os.getenv("TRAVEL_OFFLINE_STRICT"), default=False),
    )
    parser.add_argument(
        "--offline-tool-install-dir",
        default=os.getenv("TRAVEL_OFFLINE_TOOL_INSTALL_DIR", "var/offline_tools/bin"),
    )
    parser.add_argument("--bundle-skip-docker-images", action="store_true")
    parser.add_argument("--bundle-skip-tools", action="store_true")
    parser.add_argument(
        "--bundle-tool-targets",
        default=os.getenv("TRAVEL_BUNDLE_TOOL_TARGETS", "windows-amd64,linux-amd64,darwin-amd64,darwin-arm64"),
    )
    parser.add_argument("--bundle-kubectl-version", default=os.getenv("TRAVEL_BUNDLE_KUBECTL_VERSION", "v1.31.1"))
    parser.add_argument("--bundle-kind-version", default=os.getenv("TRAVEL_BUNDLE_KIND_VERSION", "v0.29.0"))
    parser.add_argument("--bundle-docker-installer-windows", default=os.getenv("TRAVEL_BUNDLE_DOCKER_INSTALLER_WINDOWS"))
    parser.add_argument("--bundle-docker-installer-linux", default=os.getenv("TRAVEL_BUNDLE_DOCKER_INSTALLER_LINUX"))
    parser.add_argument("--bundle-docker-installer-macos", default=os.getenv("TRAVEL_BUNDLE_DOCKER_INSTALLER_MACOS"))
    parser.add_argument("--k8s-provider", choices=["kind", "rancher-desktop"], default=os.getenv("TRAVEL_K8S_PROVIDER", "kind"))
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    compose_dir = root / "platform" / "deploy"
    compose_file = compose_dir / "docker-compose.yml"
    k8s_local_dir = root / "platform" / "deploy" / "k8s" / "local"
    offline_bundle_dir = Path(args.offline_bundle_dir)
    if not offline_bundle_dir.is_absolute():
        offline_bundle_dir = root / offline_bundle_dir
    manifest_path = Path(args.artifact_manifest)
    if not manifest_path.is_absolute():
        manifest_path = offline_bundle_dir / manifest_path
    offline_tool_install_dir = Path(args.offline_tool_install_dir)
    if not offline_tool_install_dir.is_absolute():
        offline_tool_install_dir = root / offline_tool_install_dir

    if args.package_mode == "prepare":
        if not args.bundle_skip_docker_images:
            _ensure_tool("docker", args.skip_install)
            _run(["docker", "info"])
            _build_runtime_images(root)
        bundle_cmd = [
            sys.executable,
            "-u",
            str(root / "platform" / "deploy" / "scripts" / "offline_bundle.py"),
            "--project-root",
            str(root),
            "--bundle-dir",
            str(offline_bundle_dir),
            "--compose-file",
            str(compose_file),
            "--tool-targets",
            args.bundle_tool_targets,
            "--kubectl-version",
            args.bundle_kubectl_version,
            "--kind-version",
            args.bundle_kind_version,
        ]
        if args.bundle_skip_docker_images:
            bundle_cmd.append("--skip-docker-images")
        if args.bundle_skip_tools:
            bundle_cmd.append("--skip-tools")
        if args.bundle_docker_installer_windows:
            bundle_cmd.extend(["--docker-installer-windows", args.bundle_docker_installer_windows])
        if args.bundle_docker_installer_linux:
            bundle_cmd.extend(["--docker-installer-linux", args.bundle_docker_installer_linux])
        if args.bundle_docker_installer_macos:
            bundle_cmd.extend(["--docker-installer-macos", args.bundle_docker_installer_macos])
        _run(
            bundle_cmd
        )
        print("[one-click] offline bundle prepared")
        return 0

    if args.package_mode == "offline":
        _install_offline_tools(offline_bundle_dir, offline_tool_install_dir, args.offline_strict)
        os.environ["PATH"] = f"{offline_tool_install_dir}{os.pathsep}{os.environ.get('PATH', '')}"

    _ensure_tool("docker", args.skip_install)
    _run(["docker", "info"])
    _run(["docker", "compose", "version"])

    if args.package_mode == "online":
        _build_runtime_images(root)

    if args.package_mode == "offline":
        if not offline_bundle_dir.exists():
            raise RuntimeError(f"offline bundle dir not found: {offline_bundle_dir}")
        manifest = _verify_manifest(offline_bundle_dir, manifest_path, args.offline_strict)
        _load_offline_images(offline_bundle_dir, manifest, args.offline_strict)
        _run(["docker", "compose", "up", "-d", "--pull", "never"], cwd=compose_dir)
    else:
        _run(["docker", "compose", "up", "-d"], cwd=compose_dir)
    _run([sys.executable, "-u", str(root / "platform" / "deploy" / "scripts" / "manual_infra_checks.py")])

    benchmark_input = root / "stress" / "report_local_one_click.json"
    if not args.skip_load_test:
        _run(
            [
                sys.executable,
                "-u",
                str(root / "stress" / "load_test.py"),
                "--base-url",
                "http://127.0.0.1:8000",
                "--requests",
                str(args.load_requests),
                "--concurrency",
                str(args.load_concurrency),
                "--out",
                str(benchmark_input),
            ]
        )

    _run(
        [
            sys.executable,
            "-u",
            str(root / "stress" / "distributed_benchmark_ingest.py"),
            "--project-root",
            str(root),
            "--input-json",
            str(benchmark_input.relative_to(root)),
            "--schema",
            "native",
            "--target-concurrency",
            str(args.load_concurrency),
            "--run-id",
            args.run_id,
            "--environment",
            args.environment,
            "--signing-key-env",
            args.signing_key_env,
        ]
    )

    fault_sample = root / "stress" / "fault_drill_local_input.json"
    _create_fault_sample(fault_sample)
    _run(
        [
            sys.executable,
            "-u",
            str(root / "stress" / "fault_drill_evidence_ingest.py"),
            "--project-root",
            str(root),
            "--input-json",
            str(fault_sample.relative_to(root)),
            "--benchmark-input-json",
            str(benchmark_input.relative_to(root)),
            "--benchmark-schema",
            "native",
            "--benchmark-target-concurrency",
            str(args.load_concurrency),
            "--run-id",
            args.run_id,
            "--environment",
            args.environment,
            "--signing-key-env",
            args.signing_key_env,
        ]
    )

    if not args.skip_k8s:
        _ensure_tool("kubectl", args.skip_install)
        if args.k8s_provider == "kind":
            _ensure_tool("kind", args.skip_install)
            cluster_name = "enterprise-travel-agent"
            list_rc = _run(["kind", "get", "clusters"], check=False)
            if list_rc == 0:
                clusters = subprocess.check_output(["kind", "get", "clusters"], text=True).splitlines()
            else:
                clusters = []
            if cluster_name not in clusters:
                _run(["kind", "create", "cluster", "--name", cluster_name])
            _run(["kind", "load", "docker-image", "enterprise-travel-agent-api:local", "--name", cluster_name])
        else:
            _run(["kubectl", "cluster-info"])

        _run(["kubectl", "apply", "-f", str(k8s_local_dir / "namespace.yaml")])
        _run(["kubectl", "apply", "-f", str(k8s_local_dir / "deployment.yaml")])
        _run(["kubectl", "apply", "-f", str(k8s_local_dir / "service.yaml")])
        _run(["kubectl", "-n", "travel-local", "rollout", "status", "deployment/travel-agent-api-local", "--timeout=180s"])

    print("[one-click] completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

