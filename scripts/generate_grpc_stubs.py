"""Generate gRPC protobuf contracts for Python and Go services.

Usage:
  python scripts/generate_grpc_stubs.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("[grpc-codegen]", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def grpc_include_dir() -> Path:
    import grpc_tools  # type: ignore

    return Path(grpc_tools.__file__).resolve().parent / "_proto"


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    proto_dir = repo / "data-contracts" / "grpc" / "v1"
    py_out = repo / "services" / "techgroup-enterprise-travel-runtime" / "src" / "travel_agent" / "grpc" / "generated" / "v1"
    policy_go_out = repo / "services" / "techgroup-enterprise-travel-policy-go" / "internal" / "grpcgen" / "v1"
    ranker_go_out = repo / "services" / "techgroup-enterprise-travel-ranker-go" / "internal" / "grpcgen" / "v1"

    py_out.mkdir(parents=True, exist_ok=True)
    policy_go_out.mkdir(parents=True, exist_ok=True)
    ranker_go_out.mkdir(parents=True, exist_ok=True)

    grpc_include = grpc_include_dir()

    # Python codegen for runtime contracts and cross-service clients.
    run(
        [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            "-I",
            str(proto_dir),
            "-I",
            str(grpc_include),
            "--python_out",
            str(py_out),
            "--grpc_python_out",
            str(py_out),
            str(proto_dir / "common.proto"),
            str(proto_dir / "runtime.proto"),
            str(proto_dir / "policy.proto"),
            str(proto_dir / "ranker.proto"),
        ]
    )

    go_plugin = shutil.which("protoc-gen-go") or str(Path(os.environ.get("GOPATH", "")) / "bin" / "protoc-gen-go.exe")
    go_grpc_plugin = shutil.which("protoc-gen-go-grpc") or str(Path(os.environ.get("GOPATH", "")) / "bin" / "protoc-gen-go-grpc.exe")
    if not Path(go_plugin).exists() or not Path(go_grpc_plugin).exists():
        print("[grpc-codegen] skip Go codegen: protoc-gen-go or protoc-gen-go-grpc not found")
        return 0

    # Go codegen for policy service.
    run(
        [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            "-I",
            str(proto_dir),
            "-I",
            str(grpc_include),
            f"--plugin=protoc-gen-go={go_plugin}",
            f"--plugin=protoc-gen-go-grpc={go_grpc_plugin}",
            "--go_out",
            str(policy_go_out),
            "--go-grpc_out",
            str(policy_go_out),
            "--go_opt=paths=source_relative",
            "--go-grpc_opt=paths=source_relative",
            str(proto_dir / "common.proto"),
            str(proto_dir / "policy.proto"),
        ]
    )

    # Go codegen for ranker service.
    run(
        [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            "-I",
            str(proto_dir),
            f"--plugin=protoc-gen-go={go_plugin}",
            f"--plugin=protoc-gen-go-grpc={go_grpc_plugin}",
            "--go_out",
            str(ranker_go_out),
            "--go-grpc_out",
            str(ranker_go_out),
            "--go_opt=paths=source_relative",
            "--go-grpc_opt=paths=source_relative",
            str(proto_dir / "ranker.proto"),
        ]
    )

    print("[grpc-codegen] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

