"""Module provides service components and helpers."""

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List


EVENT_REASONS = {
    "event_consumer_metrics_missing",
    "event_consumer_lag_exceeds_threshold",
    "event_consumer_dlq_exceeds_threshold",
    "event_consumer_no_processed_events",
    "event_consumer_handler_failures_detected",
}


def load_decision(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def requires_safemode(action: str, reasons: List[str]) -> bool:
    if action != "rollback":
        return False
    return any(reason in EVENT_REASONS for reason in reasons)


def write_runtime_override(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "TRAVEL_EVENT_BUS=local\n"
        "TRAVEL_VECTOR_BACKEND=local\n"
        "TRAVEL_EVENT_CONSUMER_ENABLE_DLQ=true\n",
        encoding="utf-8",
    )


def write_incident(path: Path, action: str, reasons: List[str], override_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": int(time.time()),
        "action": action,
        "reasons": reasons,
        "safemode_override": str(override_path),
        "owner": "release-manager",
        "status": "open",
        "next_step": "Apply override, hold promotion, start incident review",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply P3.5 autosafemode when canary gate fails on event reasons")
    parser.add_argument("--decision", default="stress/canary_gate_decision.json")
    parser.add_argument("--override-out", default="platform/deploy/runtime-overrides.env")
    parser.add_argument("--incident-out", default="stress/p3_5_incident_ticket.json")
    args = parser.parse_args()

    decision = load_decision(Path(args.decision))
    action = str(decision.get("action", "rollback"))
    raw_reasons = decision.get("reasons", [])
    reasons = [str(item) for item in raw_reasons] if isinstance(raw_reasons, list) else []

    if not requires_safemode(action, reasons):
        print("autosafemode: no action")
        return

    override_path = Path(args.override_out)
    write_runtime_override(override_path)
    write_incident(Path(args.incident_out), action, reasons, override_path)
    print(f"autosafemode: wrote {override_path}")
    print(f"autosafemode: incident ticket {args.incident_out}")


if __name__ == "__main__":
    main()

