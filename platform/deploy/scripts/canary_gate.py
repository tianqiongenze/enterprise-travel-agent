"""Module provides service components and helpers."""

import argparse
import json
from pathlib import Path
import time
from typing import Dict, List
from urllib import request


def load_report(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_prometheus_metrics(path: Path) -> Dict[str, float]:
    if not path.exists():
        return {}
    metrics: Dict[str, float] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        name, value = parts
        try:
            metrics[name] = float(value)
        except ValueError:
            continue
    return metrics


def compute_drift(summary: dict, legacy_key: str, new_key: str) -> float:
    legacy = float(summary.get(legacy_key, 0.0))
    new = float(summary.get(new_key, 0.0))
    if legacy <= 0:
        return 0.0
    return (new - legacy) / legacy


def evaluate(summary, max_success_gap: float, max_p95_drift: float, max_p99_drift: float):
    reasons = list(summary.get("fail_reasons", []))
    success_gap = float(summary.get("success_rate_gap", 0.0))
    if success_gap > max_success_gap:
        reasons.append("success_gap_exceeds_threshold")

    legacy_p95 = float(summary.get("legacy_p95_latency_ms", 0.0))
    new_p95 = float(summary.get("new_p95_latency_ms", 0.0))
    legacy_p99 = float(summary.get("legacy_p99_latency_ms", 0.0))
    new_p99 = float(summary.get("new_p99_latency_ms", 0.0))

    p95_drift = compute_drift(summary, "legacy_p95_latency_ms", "new_p95_latency_ms")
    p99_drift = compute_drift(summary, "legacy_p99_latency_ms", "new_p99_latency_ms")

    if legacy_p95 > 0 and p95_drift > max_p95_drift:
        reasons.append("p95_drift_exceeds_threshold")
    if legacy_p99 > 0 and p99_drift > max_p99_drift:
        reasons.append("p99_drift_exceeds_threshold")

    status = "promote" if not reasons else "rollback"
    return status, reasons


def evaluate_event_consumer(metrics: Dict[str, float], max_lag_seconds: float, max_dlq_increase: float) -> List[str]:
    reasons: List[str] = []
    if not metrics:
        reasons.append("event_consumer_metrics_missing")
        return reasons

    lag = float(metrics.get("travel_event_consumer_lag_seconds", 0.0))
    dlq_total = float(metrics.get("travel_event_consumer_dlq_total", 0.0))
    processed_total = float(metrics.get("travel_event_consumer_processed_total", 0.0))
    handler_failures = float(metrics.get("travel_event_consumer_handler_failures_total", 0.0))

    if lag > max_lag_seconds:
        reasons.append("event_consumer_lag_exceeds_threshold")
    if dlq_total > max_dlq_increase:
        reasons.append("event_consumer_dlq_exceeds_threshold")
    if processed_total <= 0:
        reasons.append("event_consumer_no_processed_events")
    if handler_failures > 0:
        reasons.append("event_consumer_handler_failures_detected")
    return reasons


def build_metrics(action: str, reasons: List[str], summary: Dict, thresholds: Dict, consumer_metrics: Dict[str, float]) -> str:
    p95_drift = compute_drift(summary, "legacy_p95_latency_ms", "new_p95_latency_ms")
    p99_drift = compute_drift(summary, "legacy_p99_latency_ms", "new_p99_latency_ms")
    success_gap = float(summary.get("success_rate_gap", 0.0))
    now_unix = int(time.time())

    promote = 1 if action == "promote" else 0
    rollback = 1 if action == "rollback" else 0

    lag = float(consumer_metrics.get("travel_event_consumer_lag_seconds", 0.0))
    dlq = float(consumer_metrics.get("travel_event_consumer_dlq_total", 0.0))
    processed = float(consumer_metrics.get("travel_event_consumer_processed_total", 0.0))
    failures = float(consumer_metrics.get("travel_event_consumer_handler_failures_total", 0.0))

    lines = [
        "# HELP canary_gate_status Canary gate status, 1=promote, 0=rollback",
        "# TYPE canary_gate_status gauge",
        f"canary_gate_status {promote}",
        "# HELP canary_gate_action Canary gate action one-hot metric",
        "# TYPE canary_gate_action gauge",
        f'canary_gate_action{{action="promote"}} {promote}',
        f'canary_gate_action{{action="rollback"}} {rollback}',
        "# HELP canary_gate_reason_count Number of gate failure reasons",
        "# TYPE canary_gate_reason_count gauge",
        f"canary_gate_reason_count {len(reasons)}",
        "# HELP canary_gate_success_rate_gap Observed success rate gap between legacy and new",
        "# TYPE canary_gate_success_rate_gap gauge",
        f"canary_gate_success_rate_gap {success_gap}",
        "# HELP canary_gate_p95_drift_ratio Canary p95 drift ratio against legacy",
        "# TYPE canary_gate_p95_drift_ratio gauge",
        f"canary_gate_p95_drift_ratio {p95_drift}",
        "# HELP canary_gate_p99_drift_ratio Canary p99 drift ratio against legacy",
        "# TYPE canary_gate_p99_drift_ratio gauge",
        f"canary_gate_p99_drift_ratio {p99_drift}",
        "# HELP canary_gate_threshold_success_gap Configured success gap threshold",
        "# TYPE canary_gate_threshold_success_gap gauge",
        f"canary_gate_threshold_success_gap {float(thresholds['max_success_gap'])}",
        "# HELP canary_gate_threshold_p95_drift Configured p95 drift threshold",
        "# TYPE canary_gate_threshold_p95_drift gauge",
        f"canary_gate_threshold_p95_drift {float(thresholds['max_p95_drift'])}",
        "# HELP canary_gate_threshold_p99_drift Configured p99 drift threshold",
        "# TYPE canary_gate_threshold_p99_drift gauge",
        f"canary_gate_threshold_p99_drift {float(thresholds['max_p99_drift'])}",
        "# HELP canary_gate_last_eval_timestamp Last gate evaluation unix timestamp",
        "# TYPE canary_gate_last_eval_timestamp gauge",
        f"canary_gate_last_eval_timestamp {float(now_unix)}",
        "# HELP canary_gate_event_consumer_lag_seconds Event consumer lag seen by gate",
        "# TYPE canary_gate_event_consumer_lag_seconds gauge",
        f"canary_gate_event_consumer_lag_seconds {lag}",
        "# HELP canary_gate_event_consumer_dlq_total Event consumer DLQ count seen by gate",
        "# TYPE canary_gate_event_consumer_dlq_total gauge",
        f"canary_gate_event_consumer_dlq_total {dlq}",
        "# HELP canary_gate_event_consumer_processed_total Event consumer processed count seen by gate",
        "# TYPE canary_gate_event_consumer_processed_total gauge",
        f"canary_gate_event_consumer_processed_total {processed}",
        "# HELP canary_gate_event_consumer_handler_failures_total Event consumer handler failure count seen by gate",
        "# TYPE canary_gate_event_consumer_handler_failures_total gauge",
        f"canary_gate_event_consumer_handler_failures_total {failures}",
    ]
    return "\n".join(lines) + "\n"


def maybe_write_metrics(metrics_out: str, metrics_body: str) -> None:
    if not metrics_out:
        return
    path = Path(metrics_out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(metrics_body, encoding="utf-8")


def maybe_push_metrics(pushgateway_url: str, pushgateway_job: str, metrics_body: str) -> None:
    if not pushgateway_url:
        return
    base = pushgateway_url.rstrip("/")
    endpoint = f"{base}/metrics/job/{pushgateway_job}"
    req = request.Request(
        endpoint,
        data=metrics_body.encode("utf-8"),
        method="PUT",
        headers={"Content-Type": "text/plain; version=0.0.4"},
    )
    with request.urlopen(req, timeout=5):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate canary report and output promote/rollback action")
    parser.add_argument("--report", default="stress/etcd_migration_compare.json")
    parser.add_argument("--max-success-gap", type=float, default=0.03)
    parser.add_argument("--max-p95-drift", type=float, default=0.08)
    parser.add_argument("--max-p99-drift", type=float, default=0.10)
    parser.add_argument("--event-metrics", default="stress/pulsar_consumer_metrics.prom")
    parser.add_argument("--max-event-lag-seconds", type=float, default=60.0)
    parser.add_argument("--max-event-dlq-total", type=float, default=0.0)
    parser.add_argument("--max-runtime-error-rate", type=float, default=0.01)
    parser.add_argument("--out", default="stress/canary_gate_decision.json")
    parser.add_argument("--metrics-out", default="stress/canary_gate_metrics.prom")
    parser.add_argument("--pushgateway-url", default="")
    parser.add_argument("--pushgateway-job", default="canary_gate")
    args = parser.parse_args()

    report = load_report(Path(args.report))
    summary = report.get("summary", {})
    action, reasons = evaluate(summary, args.max_success_gap, args.max_p95_drift, args.max_p99_drift)

    consumer_metrics = load_prometheus_metrics(Path(args.event_metrics))
    reasons.extend(evaluate_event_consumer(consumer_metrics, args.max_event_lag_seconds, args.max_event_dlq_total))
    action = "promote" if not reasons else "rollback"

    thresholds: Dict[str, float] = {
        "max_success_gap": args.max_success_gap,
        "max_p95_drift": args.max_p95_drift,
        "max_p99_drift": args.max_p99_drift,
        "max_event_lag_seconds": args.max_event_lag_seconds,
        "max_event_dlq_total": args.max_event_dlq_total,
        "max_runtime_error_rate": args.max_runtime_error_rate,
    }

    runtime_error_rate = float(consumer_metrics.get("travel_runtime_error_rate", 0.0))
    if runtime_error_rate > args.max_runtime_error_rate:
        reasons.append("runtime_error_rate_exceeds_threshold")
        action = "rollback"

    output = {
        "action": action,
        "reasons": reasons,
        "thresholds": thresholds,
    }
    with open(args.out, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    metrics_body = build_metrics(action, reasons, summary, thresholds, consumer_metrics)
    maybe_write_metrics(args.metrics_out, metrics_body)
    maybe_push_metrics(args.pushgateway_url, args.pushgateway_job, metrics_body)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
