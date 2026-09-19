"""Manual infrastructure smoke checks for services, middleware, and data components."""

from __future__ import annotations

import argparse
import json
import socket
import time
from pathlib import Path
from typing import Dict, List

import requests


def _tcp_check(host: str, port: int, timeout: float) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        sock.close()


def _http_check(url: str, timeout: float) -> bool:
    try:
        response = requests.get(url, timeout=timeout)
        return 200 <= response.status_code < 500
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run manual infra smoke checks")
    parser.add_argument("--out", default="stress/manual_infra_checks_report.json")
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()

    checks: List[Dict[str, object]] = []
    timeout = args.timeout

    http_targets = [
        ("runtime-health", "http://127.0.0.1:8000/health"),
        ("gateway-health", "http://127.0.0.1:8080/api/v1/travel/health"),
        ("web", "http://127.0.0.1:5173"),
        ("nacos", "http://127.0.0.1:8848/nacos"),
        ("qdrant", "http://127.0.0.1:6333/collections"),
        ("pulsar-admin", "http://127.0.0.1:8088/admin/v2/clusters"),
    ]
    tcp_targets = [
        ("etcd", "127.0.0.1", 2379),
        ("pulsar-binary", "127.0.0.1", 6650),
        ("redis-cluster", "127.0.0.1", 7000),
    ]

    for name, url in http_targets:
        ok = _http_check(url, timeout)
        checks.append({"name": name, "kind": "http", "target": url, "pass": ok})

    for name, host, port in tcp_targets:
        ok = _tcp_check(host, port, timeout)
        checks.append({"name": name, "kind": "tcp", "target": f"{host}:{port}", "pass": ok})

    passed = len([item for item in checks if item["pass"]])
    failed = len(checks) - passed
    report = {
        "generatedAt": int(time.time()),
        "summary": {"overall": "PASS" if failed == 0 else "FAIL", "passCount": passed, "failCount": failed},
        "checks": checks,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated: {out.resolve()}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

