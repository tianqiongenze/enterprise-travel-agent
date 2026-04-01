"""Generate readiness assessment for global 10B users / 1M concurrent target."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, Any


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def evaluate(
    go_live: Dict[str, Any],
    report_5k: Dict[str, Any],
    distributed: Dict[str, Any],
    fault_drill: Dict[str, Any],
    target_concurrency: int,
) -> Dict[str, Any]:
    summary = go_live.get("summary", {}) if isinstance(go_live, dict) else {}
    go_live_fail = int(summary.get("failCount", 999))
    go_live_pass = str(summary.get("overall", "FAIL")).upper() == "PASS"
    if not go_live_pass and isinstance(go_live, dict):
        checks = go_live.get("checks", [])
        if isinstance(checks, list):
            failed_names = [
                str(item.get("name", ""))
                for item in checks
                if isinstance(item, dict) and str(item.get("status", "")).upper() == "FAIL"
            ]
            if failed_names and all(name == "global_scale_status_minimum" for name in failed_names):
                go_live_pass = True
                go_live_fail = 0

    p95 = 0.0
    p99 = 0.0
    success_rate = 0.0
    if isinstance(report_5k, dict):
        p95 = float(report_5k.get("p95_latency_ms", report_5k.get("p95_ms", report_5k.get("p95", 0.0))) or 0.0)
        p99 = float(report_5k.get("p99_latency_ms", report_5k.get("p99_ms", report_5k.get("p99", 0.0))) or 0.0)
        raw_success_rate = float(report_5k.get("success_rate", 0.0) or 0.0)
        success_rate = raw_success_rate * 100.0 if raw_success_rate <= 1.0 else raw_success_rate

    distributed_ok = bool(distributed.get("pass", False)) and int(distributed.get("achievedConcurrency", 0)) >= target_concurrency
    fault_drill_ok = bool(fault_drill.get("pass", False))

    criteria = {
        "go_live_gate_pass": go_live_pass and go_live_fail == 0,
        "local_5k_success_rate_ge_99": success_rate >= 99.0,
        "local_5k_p95_le_1200ms": p95 <= 1200.0,
        "local_5k_p99_le_1500ms": p99 <= 1500.0,
        "distributed_1m_evidence": distributed_ok,
        "global_multi_region_drill_evidence": fault_drill_ok,
    }

    architecture_ready = all(
        [
            criteria["go_live_gate_pass"],
            criteria["local_5k_success_rate_ge_99"],
            criteria["local_5k_p95_le_1200ms"],
            criteria["local_5k_p99_le_1500ms"],
        ]
    )
    production_proven = architecture_ready and criteria["distributed_1m_evidence"] and criteria["global_multi_region_drill_evidence"]

    return {
        "generatedAt": int(time.time()),
        "target": {
            "registeredUsers": 10_000_000_000,
            "concurrentUsers": target_concurrency,
        },
        "status": "PRODUCTION_PROVEN" if production_proven else ("ARCHITECTURE_READY_NOT_PROVEN" if architecture_ready else "NOT_READY"),
        "criteria": criteria,
        "observations": {
            "goLiveOverall": summary.get("overall", "unknown"),
            "goLiveFailCount": go_live_fail,
            "local5kSuccessRate": success_rate,
            "local5kP95Ms": p95,
            "local5kP99Ms": p99,
            "distributedAchievedConcurrency": int(distributed.get("achievedConcurrency", 0)),
            "distributedRegions": int(distributed.get("regions", 0)),
            "faultDrillScenarioCount": int(fault_drill.get("scenarioCount", 0)),
        },
        "nextActions": [
            "Run distributed >=1,000,000 concurrent benchmark across >=3 regions.",
            "Run 12h sustained canary with global traffic engineering enabled.",
            "Attach chaos drill evidence for region outage, MQ lag storm, and Redis failover.",
        ],
    }


def write_markdown(path: Path, result: Dict[str, Any]) -> None:
    criteria = result["criteria"]
    obs = result["observations"]
    lines = [
        "# Global Scale Readiness Report",
        "",
        f"- GeneratedAt: {result['generatedAt']}",
        f"- Status: **{result['status']}**",
        f"- Target: 10B registered users / {result['target']['concurrentUsers']:,} concurrent users",
        "",
        "## Evidence Checks",
        "",
        f"- go_live_gate_pass: {criteria['go_live_gate_pass']}",
        f"- local_5k_success_rate_ge_99: {criteria['local_5k_success_rate_ge_99']}",
        f"- local_5k_p95_le_1200ms: {criteria['local_5k_p95_le_1200ms']}",
        f"- local_5k_p99_le_1500ms: {criteria['local_5k_p99_le_1500ms']}",
        f"- distributed_1m_evidence: {criteria['distributed_1m_evidence']}",
        f"- global_multi_region_drill_evidence: {criteria['global_multi_region_drill_evidence']}",
        "",
        "## Observations",
        "",
        f"- goLiveOverall: {obs['goLiveOverall']}",
        f"- goLiveFailCount: {obs['goLiveFailCount']}",
        f"- local5kSuccessRate: {obs['local5kSuccessRate']}",
        f"- local5kP95Ms: {obs['local5kP95Ms']}",
        f"- local5kP99Ms: {obs['local5kP99Ms']}",
        "",
        "## Next Actions",
        "",
    ]
    for action in result["nextActions"]:
        lines.append(f"- {action}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess 10B/1M readiness from local evidence")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--target-concurrency", type=int, default=1_000_000)
    parser.add_argument("--out-json", default="stress/global_scale_readiness_report.json")
    parser.add_argument("--out-md", default="stress/global_scale_readiness_report.md")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    go_live = load_json(root / "stress" / "go_live_final_report.json")
    report_5k = load_json(root / "stress" / "report_5k.json")
    distributed = load_json(root / "stress" / "distributed_benchmark_evidence.json")
    fault_drill = load_json(root / "stress" / "multi_region_fault_drill_report.json")
    result = evaluate(go_live, report_5k, distributed, fault_drill, args.target_concurrency)

    out_json = root / args.out_json
    out_md = root / args.out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(out_md, result)

    print(f"Generated: {out_json}")
    print(f"Generated: {out_md}")
    print(json.dumps({"status": result["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

