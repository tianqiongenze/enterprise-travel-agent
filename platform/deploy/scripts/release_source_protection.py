"""Build an encrypted source bundle for hardened production releases.

This script does not modify runtime code paths. It creates a protected archive-like
artifact for release governance, escrow, and compliance handoff.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

from cryptography.fernet import Fernet


INCLUDE_EXTENSIONS = {
    ".py",
    ".go",
    ".java",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".proto",
    ".sql",
    ".sh",
    ".ps1",
    ".yaml",
    ".yml",
    ".wxml",
    ".wxss",
}

SKIP_SEGMENTS = {
    ".git",
    "node_modules",
    "target",
    "dist",
    "build",
    "__pycache__",
    ".idea",
    ".vscode",
    "tools/jdtls",
    "var/release_hardening",
}


@dataclass
class ProtectedFile:
    path: str
    output: str
    plainSha256: str
    cipherSha256: str
    plainSize: int


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_skipped(path: Path, root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    for segment in SKIP_SEGMENTS:
        if segment in rel:
            return True
    return False


def iter_source_files(root: Path) -> Iterable[Path]:
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if _is_skipped(file_path, root):
            continue
        if file_path.suffix.lower() not in INCLUDE_EXTENSIONS:
            continue
        yield file_path


def build_cipher_from_secret(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def protect_sources(project_root: Path, out_dir: Path, secret: str) -> dict:
    cipher = build_cipher_from_secret(secret)
    files: List[ProtectedFile] = []

    obf_root = out_dir / "encrypted_sources"
    obf_root.mkdir(parents=True, exist_ok=True)

    for source_path in iter_source_files(project_root):
        raw = source_path.read_bytes()
        encrypted = cipher.encrypt(raw)
        rel = source_path.relative_to(project_root)
        dst = obf_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst = dst.with_suffix(dst.suffix + ".enc")
        dst.write_bytes(encrypted)
        files.append(
            ProtectedFile(
                path=rel.as_posix(),
                output=dst.relative_to(project_root).as_posix(),
                plainSha256=_sha256(raw),
                cipherSha256=_sha256(encrypted),
                plainSize=len(raw),
            )
        )

    manifest = {
        "generatedAt": int(time.time()),
        "mode": "release-source-encryption",
        "fileCount": len(files),
        "outputRoot": obf_root.relative_to(project_root).as_posix(),
        "files": [asdict(item) for item in files],
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build encrypted source bundle for release hardening")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--out-dir", default="var/release_hardening")
    parser.add_argument("--secret-env", default="TRAVEL_RELEASE_SOURCE_KEY")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    out_dir = (project_root / args.out_dir).resolve()
    secret = os.getenv(args.secret_env, "").strip()
    if not secret:
        raise SystemExit(f"missing required secret env: {args.secret_env}")

    manifest = protect_sources(project_root, out_dir, secret)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "source_protection_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[release-hardening] protected files={manifest['fileCount']}")
    print(f"[release-hardening] manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

