"""CI guard: regenerate gRPC stubs and fail when tracked generated files drift."""

from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("[grpc-drift]", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def capture(cmd: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def main() -> int:
    repo = Path(__file__).resolve().parents[1]

    # 1) Regenerate Python + Go stubs.
    run([sys.executable, str(repo / "scripts" / "generate_grpc_stubs.py")], cwd=repo)

    # 2) Ensure Java proto generation still works.
    if os.name == "nt":
        run([
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo / "scripts" / "generate_grpc_java_stubs.ps1"),
        ], cwd=repo)
    else:
        run(["mvn", "-q", "generate-sources"], cwd=repo / "services" / "techgroup-enterprise-travel-gateway")

    # 3) Drift check on tracked proto + generated Python/Go artifacts.
    tracked = capture(
        [
            "git",
            "--no-pager",
            "ls-files",
            "data-contracts/grpc/v1/*.proto",
            "services/techgroup-enterprise-travel-runtime/src/travel_agent/grpc/generated/v1/*.py",
            "services/techgroup-enterprise-travel-policy-go/internal/grpcgen/v1/*.go",
            "services/techgroup-enterprise-travel-ranker-go/internal/grpcgen/v1/*.go",
        ],
        cwd=repo,
    ).splitlines()
    tracked = [line.strip() for line in tracked if line.strip()]
    if not tracked:
        print("[grpc-drift] no tracked files to check")
        return 0

    cmd = ["git", "--no-pager", "diff", "--exit-code", "--", *tracked]
    completed = subprocess.run(cmd, cwd=str(repo), text=True, capture_output=True)
    if completed.returncode != 0:
        print("[grpc-drift] generated artifacts drift detected")
        changed = capture(["git", "--no-pager", "diff", "--name-only", "--", *tracked], cwd=repo).splitlines()
        if changed:
            print("[grpc-drift] changed files:")
            for path in changed:
                print(f"  - {path}")
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr)
        return completed.returncode

    print("[grpc-drift] clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

