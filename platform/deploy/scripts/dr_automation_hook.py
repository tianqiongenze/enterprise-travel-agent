"""Trigger DR automation hooks from fault-drill evidence."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Handle DR automation hook from evidence artifact")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--incident-out", default="stress/dr_automation_incident.json")
    parser.add_argument("--status-out", default="stress/dr_automation_status.json")
    parser.add_argument("--auto-run", action="store_true", default=False)
    args = parser.parse_args()

    evidence_path = Path(args.evidence)
    payload = _load_json(evidence_path)
    if not payload:
        return 1

    passed = bool(payload.get("pass", False))
    status = {
        "timestamp": int(time.time()),
        "evidence": str(evidence_path.resolve()),
        "pass": passed,
        "action": "none" if passed else "trigger-dr-playbook",
    }
    status_path = Path(args.status_out)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    if passed:
        print(json.dumps(status, ensure_ascii=False))
        return 0

    incident = {
        "timestamp": int(time.time()),
        "status": "open",
        "severity": "critical",
        "reason": "multi_region_fault_drill_failed",
        "evidence": str(evidence_path.resolve()),
        "next_step": "Execute DR runbook and regional failover validation",
        "autoRun": bool(args.auto_run),
    }
    incident_path = Path(args.incident_out)
    incident_path.parent.mkdir(parents=True, exist_ok=True)
    incident_path.write_text(json.dumps(incident, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
