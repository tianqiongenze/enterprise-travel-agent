"""Prepare an offline artifact bundle for one-click stack deployment."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


IMAGE_PATTERN = re.compile(r"^\s*image\s*:\s*(.+?)\s*$")
TARGETS_DEFAULT = ["windows-amd64", "linux-amd64", "darwin-amd64", "darwin-arm64"]


def _run(cmd: list[str], check: bool = True) -> int:
    print("[run]", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}")
    return result.returncode


def _image_exists(image: str) -> bool:
    return _run(["docker", "image", "inspect", image], check=False) == 0


def _download(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[download] {url} -> {output_path}")
    with urllib.request.urlopen(url) as response:
        output_path.write_bytes(response.read())


def _target_tools(target: str, kubectl_version: str, kind_version: str) -> list[dict[str, str]]:
    mapping = {
        "windows-amd64": [
            {
                "name": "kubectl",
                "url": f"https://dl.k8s.io/release/{kubectl_version}/bin/windows/amd64/kubectl.exe",
                "filename": "kubectl.exe",
            },
            {
                "name": "kind",
                "url": f"https://kind.sigs.k8s.io/dl/{kind_version}/kind-windows-amd64",
                "filename": "kind.exe",
            },
        ],
        "linux-amd64": [
            {
                "name": "kubectl",
                "url": f"https://dl.k8s.io/release/{kubectl_version}/bin/linux/amd64/kubectl",
                "filename": "kubectl",
            },
            {
                "name": "kind",
                "url": f"https://kind.sigs.k8s.io/dl/{kind_version}/kind-linux-amd64",
                "filename": "kind",
            },
        ],
        "darwin-amd64": [
            {
                "name": "kubectl",
                "url": f"https://dl.k8s.io/release/{kubectl_version}/bin/darwin/amd64/kubectl",
                "filename": "kubectl",
            },
            {
                "name": "kind",
                "url": f"https://kind.sigs.k8s.io/dl/{kind_version}/kind-darwin-amd64",
                "filename": "kind",
            },
        ],
        "darwin-arm64": [
            {
                "name": "kubectl",
                "url": f"https://dl.k8s.io/release/{kubectl_version}/bin/darwin/arm64/kubectl",
                "filename": "kubectl",
            },
            {
                "name": "kind",
                "url": f"https://kind.sigs.k8s.io/dl/{kind_version}/kind-darwin-arm64",
                "filename": "kind",
            },
        ],
    }
    if target not in mapping:
        raise RuntimeError(f"unsupported tool target: {target}")
    return mapping[target]


def _collect_tools(
    bundle_dir: Path,
    targets: list[str],
    kubectl_version: str,
    kind_version: str,
    docker_installer_windows: Path | None,
    docker_installer_linux: Path | None,
    docker_installer_macos: Path | None,
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for target in targets:
        target_dir = bundle_dir / "tools" / target
        target_dir.mkdir(parents=True, exist_ok=True)
        for tool in _target_tools(target, kubectl_version, kind_version):
            output_path = target_dir / tool["filename"]
            _download(tool["url"], output_path)
            records.append(
                {
                    "target": target,
                    "name": tool["name"],
                    "path": output_path.relative_to(bundle_dir).as_posix(),
                }
            )

    if docker_installer_windows and docker_installer_windows.exists():
        dst = bundle_dir / "tools" / "windows-amd64" / "docker-desktop-installer.exe"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(docker_installer_windows, dst)
        records.append({"target": "windows-amd64", "name": "docker-installer", "path": dst.relative_to(bundle_dir).as_posix()})

    if docker_installer_linux and docker_installer_linux.exists():
        dst = bundle_dir / "tools" / "linux-amd64" / "docker-linux-installer.tgz"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(docker_installer_linux, dst)
        records.append({"target": "linux-amd64", "name": "docker-installer", "path": dst.relative_to(bundle_dir).as_posix()})

    if docker_installer_macos and docker_installer_macos.exists():
        dst = bundle_dir / "tools" / "darwin-amd64" / "docker-desktop-installer.dmg"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(docker_installer_macos, dst)
        records.append({"target": "darwin-amd64", "name": "docker-installer", "path": dst.relative_to(bundle_dir).as_posix()})
        dst_arm = bundle_dir / "tools" / "darwin-arm64" / "docker-desktop-installer.dmg"
        dst_arm.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(docker_installer_macos, dst_arm)
        records.append({"target": "darwin-arm64", "name": "docker-installer", "path": dst_arm.relative_to(bundle_dir).as_posix()})

    return records


def _parse_compose_images(compose_file: Path) -> list[str]:
    images: list[str] = []
    for line in compose_file.read_text(encoding="utf-8").splitlines():
        match = IMAGE_PATTERN.match(line)
        if not match:
            continue
        image = match.group(1).strip().strip('"').strip("'")
        if image and image not in images:
            images.append(image)
    return images


def _safe_archive_name(image: str) -> str:
    # Convert registry/name:tag to a file-safe tar name.
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", image)
    return f"{safe}.tar"


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _write_manifest(bundle_dir: Path, images: list[dict], tools: list[dict]) -> Path:
    files: list[dict[str, str]] = []
    for file_path in sorted(bundle_dir.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.name == "artifacts.manifest.json":
            continue
        rel = file_path.relative_to(bundle_dir).as_posix()
        files.append({"path": rel, "sha256": _sha256_file(file_path)})

    manifest = {
        "version": 1,
        "generatedAt": datetime.now(tz=timezone.utc).isoformat(),
        "images": images,
        "tools": tools,
        "files": files,
    }
    manifest_path = bundle_dir / "artifacts.manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare offline bundle for one-click deployment")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--compose-file", required=True)
    parser.add_argument("--skip-docker-images", action="store_true")
    parser.add_argument("--skip-tools", action="store_true")
    parser.add_argument("--tool-targets", default=",".join(TARGETS_DEFAULT))
    parser.add_argument("--kubectl-version", default="v1.31.1")
    parser.add_argument("--kind-version", default="v0.29.0")
    parser.add_argument("--docker-installer-windows")
    parser.add_argument("--docker-installer-linux")
    parser.add_argument("--docker-installer-macos")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    compose_file = Path(args.compose_file)
    if not compose_file.is_absolute():
        compose_file = project_root / compose_file

    bundle_dir = Path(args.bundle_dir)
    if not bundle_dir.is_absolute():
        bundle_dir = project_root / bundle_dir
    image_dir = bundle_dir / "images"

    bundle_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    images_meta: list[dict] = []
    tools_meta: list[dict] = []
    images = _parse_compose_images(compose_file)
    print(f"[bundle] discovered {len(images)} image(s) from compose")

    if not args.skip_docker_images:
        _run(["docker", "info"])
        for image in images:
            if _image_exists(image):
                print(f"[bundle] use local image: {image}")
            else:
                _run(["docker", "pull", image])
            archive = _safe_archive_name(image)
            archive_path = image_dir / archive
            _run(["docker", "save", "-o", str(archive_path), image])
            images_meta.append({"name": image, "archive": f"images/{archive}"})
    else:
        print("[bundle] skip docker image pull/save by option")

    if not args.skip_tools:
        targets = [item.strip() for item in args.tool_targets.split(",") if item.strip()]
        tools_meta = _collect_tools(
            bundle_dir=bundle_dir,
            targets=targets,
            kubectl_version=args.kubectl_version,
            kind_version=args.kind_version,
            docker_installer_windows=Path(args.docker_installer_windows).resolve() if args.docker_installer_windows else None,
            docker_installer_linux=Path(args.docker_installer_linux).resolve() if args.docker_installer_linux else None,
            docker_installer_macos=Path(args.docker_installer_macos).resolve() if args.docker_installer_macos else None,
        )
        print(f"[bundle] packaged {len(tools_meta)} offline tool artifact(s)")
    else:
        print("[bundle] skip tool download by option")

    manifest_path = _write_manifest(bundle_dir, images_meta, tools_meta)
    print(f"[bundle] manifest written: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

