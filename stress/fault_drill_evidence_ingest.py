"""Ingest external fault-drill results and emit signed canonical evidence."""

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
from typing import Dict, List, Tuple

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


def _normalize_scenarios(rows: List[Dict[str, object]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "name": str(item.get("name", item.get("scenario", "unknown"))),
                "status": str(item.get("status", item.get("phase", "FAIL"))).upper(),
            }
        )
    return normalized


def _parse_native(source: Dict[str, object]) -> Tuple[List[Dict[str, str]], int, int, float, float]:
    raw = source.get("scenarios", []) if isinstance(source.get("scenarios"), list) else []
    scenarios = _normalize_scenarios(raw)
    scenario_count = int(source.get("scenarioCount", len(scenarios)) or len(scenarios))
    rto = int(source.get("recoveryRtoMinutes", 0) or 0)
    rpo = int(source.get("recoveryRpoSeconds", 0) or 0)
    lag = float(source.get("eventConsumerLagSeconds", 0.0) or 0.0)
    dlq = float(source.get("eventConsumerDlqTotal", 0.0) or 0.0)
    return scenarios, scenario_count, rto, rpo, lag, dlq


def _parse_chaosmesh(source: Dict[str, object]) -> Tuple[List[Dict[str, str]], int, int, float, float]:
    experiments = source.get("experiments", []) if isinstance(source.get("experiments"), list) else []
    scenarios = _normalize_scenarios(experiments)
    summary = source.get("summary", {}) if isinstance(source.get("summary"), dict) else {}
    scenario_count = int(summary.get("total", len(scenarios)) or len(scenarios))
    rto = int(summary.get("rtoMinutes", 0) or 0)
    rpo = int(summary.get("rpoSeconds", 0) or 0)
    lag = float(summary.get("eventLagSeconds", 0.0) or 0.0)
    dlq = float(summary.get("eventDlqTotal", 0.0) or 0.0)
    return scenarios, scenario_count, rto, rpo, lag, dlq


def _parse_litmus(source: Dict[str, object]) -> Tuple[List[Dict[str, str]], int, int, float, float]:
    runs = source.get("chaosRuns", []) if isinstance(source.get("chaosRuns"), list) else []
    scenarios = _normalize_scenarios(runs)
    scenario_count = int(source.get("scenarioCount", len(scenarios)) or len(scenarios))
    rto = int(source.get("rtoMinutes", 0) or 0)
    rpo = int(source.get("rpoSeconds", 0) or 0)
    lag = float(source.get("eventLagSeconds", 0.0) or 0.0)
    dlq = float(source.get("eventDlqTotal", 0.0) or 0.0)
    return scenarios, scenario_count, rto, rpo, lag, dlq


def _detect_schema(source: Dict[str, object]) -> str:
    if "experiments" in source:
        return "chaosmesh"
    if "chaosRuns" in source:
        return "litmus"
    return "native"


def _benchmark_gate(achieved: int, p95: float, p99: float, error_rate: float, target: int) -> bool:
    return achieved >= target and p95 <= 1200.0 and p99 <= 1500.0 and error_rate <= 1.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest fault drill result and build signed evidence")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--schema", choices=["auto", "native", "chaosmesh", "litmus"], default="auto")
    parser.add_argument("--benchmark-input-json", default="", help="Optional k6/JMeter/Locust JSON to link into fault evidence")
    parser.add_argument("--benchmark-schema", choices=["auto", "native", "k6", "jmeter", "locust"], default="auto")
    parser.add_argument("--benchmark-target-concurrency", type=int, default=0)
    parser.add_argument("--require-benchmark-pass", action="store_true")
    parser.add_argument("--evidence-source", default="chaos-drill")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", default="staging")
    parser.add_argument("--out-json", default="stress/multi_region_fault_drill_report.json")
    parser.add_argument("--out-md", default="stress/multi_region_fault_drill_report.md")
    parser.add_argument("--signing-key-env", default="TRAVEL_EVIDENCE_SIGNING_KEY")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    source = _load_json((root / args.input_json).resolve())

    schema = _detect_schema(source) if args.schema == "auto" else args.schema
    if schema == "chaosmesh":
        normalized, scenario_count, rto, rpo, lag, dlq = _parse_chaosmesh(source)
    elif schema == "litmus":
        normalized, scenario_count, rto, rpo, lag, dlq = _parse_litmus(source)
    else:
        normalized, scenario_count, rto, rpo, lag, dlq = _parse_native(source)

    passed = len([s for s in normalized if s.get("status") == "PASS"])

    pass_flag = passed == scenario_count and scenario_count >= 3 and rto <= 15 and rpo <= 60 and lag <= 60.0 and dlq <= 0.0

    linked_benchmark = None
    if args.benchmark_input_json:
        benchmark_path = (root / args.benchmark_input_json).resolve()
        benchmark_source = _load_json(benchmark_path)
        achieved, p95, p99, error_rate, benchmark_schema = parse_benchmark(benchmark_source, args.benchmark_schema)
        target = int(args.benchmark_target_concurrency or achieved)
        benchmark_pass = _benchmark_gate(achieved, p95, p99, error_rate, target)
        linked_benchmark = {
            "schema": benchmark_schema,
            "sourcePath": str(benchmark_path),
            "targetConcurrency": target,
            "achievedConcurrency": achieved,
            "p95Ms": p95,
            "p99Ms": p99,
            "errorRatePercent": error_rate,
            "pass": benchmark_pass,
        }
        if args.require_benchmark_pass:
            pass_flag = pass_flag and benchmark_pass

    core = {
        "generatedAt": int(time.time()),
        "evidenceKind": "multi-region-fault-drill",
        "pass": pass_flag,
        "scenarioCount": scenario_count,
        "passedScenarios": passed,
        "recoveryRtoMinutes": rto,
        "recoveryRpoSeconds": rpo,
        "eventConsumerLagSeconds": lag,
        "eventConsumerDlqTotal": dlq,
        "evidenceSource": args.evidence_source,
        "runId": args.run_id,
        "environment": args.environment,
        "schema": schema,
        "sourcePath": str((root / args.input_json).resolve()),
        "scenarios": normalized,
        "linkedBenchmark": linked_benchmark,
        "note": "Signed evidence ingested from external fault-drill output.",
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
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(
        "\n".join(
            [
                "# Multi-Region Fault Drill Evidence (Ingested)",
                "",
                f"- pass: {evidence['pass']}",
                f"- runId: {evidence['runId']}",
                f"- environment: {evidence['environment']}",
                f"- signed: {evidence['signed']}",
                f"- scenarioCount: {evidence['scenarioCount']}",
                f"- passedScenarios: {evidence['passedScenarios']}",
                f"- recoveryRtoMinutes: {evidence['recoveryRtoMinutes']}",
                f"- recoveryRpoSeconds: {evidence['recoveryRpoSeconds']}",
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

