"""Ingest external distributed benchmark results and emit signed canonical evidence.

Supported schemas:
- k6 summary json
- JMeter Dashboard statistics.json
- Locust stats export json
- native travel report json
"""

from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

if __package__ in (None, ""):
    # Executed as a script (python stress/xxx.py): make the repo root importable
    # so "from stress." package imports resolve regardless of the caller's CWD.
    _REPO_ROOT = str(_BootstrapPath(__file__).resolve().parents[1])
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)

import argparse
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

from stress.ingest_schema_adapters import parse_benchmark


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sign(payload: dict, key: str) -> str:
    return hmac.new(key.encode("utf-8"), _canonical(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest benchmark result and build signed evidence")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--target-concurrency", type=int, default=1_000_000)
    parser.add_argument("--schema", choices=["auto", "native", "k6", "jmeter", "locust"], default="auto")
    parser.add_argument("--regions", type=int, default=3)
    parser.add_argument("--duration-minutes", type=int, default=60)
    parser.add_argument("--evidence-source", default="k6-distributed")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", default="staging")
    parser.add_argument("--out-json", default="stress/distributed_benchmark_evidence.json")
    parser.add_argument("--out-md", default="stress/distributed_benchmark_evidence.md")
    parser.add_argument("--signing-key-env", default="TRAVEL_EVIDENCE_SIGNING_KEY")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    source = _load_json((root / args.input_json).resolve())

    achieved, p95, p99, error_rate, schema = parse_benchmark(source, args.schema)

    pass_flag = (
        achieved >= args.target_concurrency
        and args.regions >= 3
        and args.duration_minutes >= 60
        and p95 <= 1200.0
        and p99 <= 1500.0
        and error_rate <= 1.0
    )

    core = {
        "generatedAt": int(time.time()),
        "evidenceKind": "distributed-benchmark",
        "pass": pass_flag,
        "targetConcurrency": args.target_concurrency,
        "achievedConcurrency": achieved,
        "regions": args.regions,
        "durationMinutes": args.duration_minutes,
        "p95Ms": p95,
        "p99Ms": p99,
        "errorRatePercent": error_rate,
        "evidenceSource": args.evidence_source,
        "runId": args.run_id,
        "environment": args.environment,
        "schema": schema,
        "reportPath": str((root / args.input_json).resolve()),
        "note": "Signed evidence ingested from external benchmark output.",
    }

    key = str(os.environ.get(args.signing_key_env, "")).strip()
    signature = _sign(core, key) if key else ""
    evidence = dict(core)
    evidence["signed"] = bool(signature)
    evidence["signatureAlgorithm"] = "HMAC-SHA256" if signature else ""
    evidence["signature"] = signature

    out_json = root / args.out_json
    out_md = root / args.out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(
        "\n".join(
            [
                "# Distributed Benchmark Evidence (Ingested)",
                "",
                f"- pass: {evidence['pass']}",
                f"- runId: {evidence['runId']}",
                f"- environment: {evidence['environment']}",
                f"- signed: {evidence['signed']}",
                f"- achievedConcurrency: {evidence['achievedConcurrency']}",
                f"- p95Ms: {evidence['p95Ms']}",
                f"- p99Ms: {evidence['p99Ms']}",
                f"- errorRatePercent: {evidence['errorRatePercent']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Generated: {out_json}")
    print(f"Generated: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

