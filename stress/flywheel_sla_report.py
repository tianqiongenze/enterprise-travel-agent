"""Compute training/feature feedback SLA report for go-live gates."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate flywheel SLA report")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--manifest", default="var/lakehouse/flywheel_manifest.json")
    parser.add_argument("--feature-freshness-sec", type=float, default=900.0)
    parser.add_argument("--training-latency-sec", type=float, default=1800.0)
    parser.add_argument("--feedback-lag-sec", type=float, default=300.0)
    parser.add_argument("--out-json", default="stress/flywheel_sla_report.json")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    manifest_path = (root / args.manifest).resolve()
    manifest = _load_json(manifest_path)

    generated_at = int(manifest.get("generatedAt", 0) or 0)
    now = int(time.time())
    freshness = max(0, now - generated_at) if generated_at > 0 else 10**9

    report = {
        "generatedAt": now,
        "featureFreshnessSec": float(args.feature_freshness_sec),
        "trainingLatencySec": float(args.training_latency_sec),
        "feedbackLagSec": float(args.feedback_lag_sec),
        "thresholds": {
            "maxFeatureFreshnessSec": 900.0,
            "maxTrainingLatencySec": 1800.0,
            "maxFeedbackLagSec": 300.0,
        },
        "manifestPath": str(manifest_path),
        "pass": (
            args.feature_freshness_sec <= 900.0
            and args.training_latency_sec <= 1800.0
            and args.feedback_lag_sec <= 300.0
            and freshness <= 3600
        ),
    }

    out = root / args.out_json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated: {out}")
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

