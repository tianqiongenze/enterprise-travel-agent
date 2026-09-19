"""Generate distributed benchmark evidence for global-scale readiness gates."""

from __future__ import annotations

import argparse
import hmac
import json
import time
import hashlib
import os
from pathlib import Path


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _canonical_payload(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sign_payload(payload: dict, key: str) -> str:
    return hmac.new(key.encode("utf-8"), _canonical_payload(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build distributed benchmark evidence artifact")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--target-concurrency", type=int, default=1_000_000)
    parser.add_argument("--report-json", default="stress/report_5k.json")
    parser.add_argument("--regions", type=int, default=1)
    parser.add_argument("--duration-minutes", type=int, default=10)
    parser.add_argument("--evidence-source", default="local-loadtest")
    parser.add_argument("--run-id", default="local-unknown")
    parser.add_argument("--environment", default="local")
    parser.add_argument("--out-json", default="stress/distributed_benchmark_evidence.json")
    parser.add_argument("--out-md", default="stress/distributed_benchmark_evidence.md")
    parser.add_argument("--signing-key-env", default="TRAVEL_EVIDENCE_SIGNING_KEY")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    report = _load_json((root / args.report_json).resolve())
    achieved_concurrency = int(report.get("concurrency", 0) or 0)
    p95_ms = float(report.get("p95_latency_ms", report.get("p95_ms", report.get("p95", 0.0))) or 0.0)
    p99_ms = float(report.get("p99_latency_ms", report.get("p99_ms", report.get("p99", 0.0))) or 0.0)
    raw_success_rate = float(report.get("success_rate", 0.0) or 0.0)
    success_rate_percent = raw_success_rate * 100.0 if raw_success_rate <= 1.0 else raw_success_rate
    error_rate_percent = max(0.0, 100.0 - success_rate_percent)

    pass_flag = (
        achieved_concurrency >= args.target_concurrency
        and args.regions >= 3
        and args.duration_minutes >= 60
        and p95_ms <= 1200.0
        and p99_ms <= 1500.0
        and error_rate_percent <= 1.0
    )

    core = {
        "generatedAt": int(time.time()),
        "evidenceKind": "distributed-benchmark",
        "pass": pass_flag,
        "targetConcurrency": args.target_concurrency,
        "achievedConcurrency": achieved_concurrency,
        "regions": args.regions,
        "durationMinutes": args.duration_minutes,
        "p95Ms": p95_ms,
        "p99Ms": p99_ms,
        "errorRatePercent": error_rate_percent,
        "evidenceSource": args.evidence_source,
        "runId": args.run_id,
        "environment": args.environment,
        "reportPath": str((root / args.report_json).resolve()),
        "note": "Measured evidence generated from report artifacts. Avoid synthetic defaults.",
    }

    key = str(os.environ.get(args.signing_key_env, "")).strip()
    signature = _sign_payload(core, key) if key else ""
    result = dict(core)
    result["signed"] = bool(signature)
    result["signatureAlgorithm"] = "HMAC-SHA256" if signature else ""
    result["signature"] = signature

    out_json = root / args.out_json
    out_md = root / args.out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Distributed Benchmark Evidence",
        "",
        f"- pass: {result['pass']}",
        f"- targetConcurrency: {result['targetConcurrency']}",
        f"- achievedConcurrency: {result['achievedConcurrency']}",
        f"- regions: {result['regions']}",
        f"- durationMinutes: {result['durationMinutes']}",
        f"- p95Ms: {result['p95Ms']}",
        f"- p99Ms: {result['p99Ms']}",
        f"- errorRatePercent: {result['errorRatePercent']}",
        f"- evidenceSource: {result['evidenceSource']}",
        f"- runId: {result['runId']}",
        f"- environment: {result['environment']}",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Generated: {out_json}")
    print(f"Generated: {out_md}")
    print(json.dumps({"pass": pass_flag}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

