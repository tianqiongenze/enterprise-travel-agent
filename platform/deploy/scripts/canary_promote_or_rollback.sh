#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
REPORT_PATH="${1:-$ROOT_DIR/stress/etcd_migration_compare.json}"
METRICS_OUT="${CANARY_GATE_METRICS_OUT:-$ROOT_DIR/stress/canary_gate_metrics.prom}"
PUSHGATEWAY_URL="${CANARY_GATE_PUSHGATEWAY_URL:-}"
PUSHGATEWAY_JOB="${CANARY_GATE_PUSHGATEWAY_JOB:-canary_gate}"
EVENT_METRICS="${CANARY_EVENT_METRICS_PATH:-$ROOT_DIR/stress/pulsar_consumer_metrics.prom}"
MAX_EVENT_LAG="${CANARY_MAX_EVENT_LAG_SECONDS:-60}"
MAX_EVENT_DLQ="${CANARY_MAX_EVENT_DLQ_TOTAL:-0}"

python3 "$ROOT_DIR/platform/deploy/scripts/canary_gate.py" \
  --report "$REPORT_PATH" \
  --out "$ROOT_DIR/stress/canary_gate_decision.json" \
  --event-metrics "$EVENT_METRICS" \
  --max-event-lag-seconds "$MAX_EVENT_LAG" \
  --max-event-dlq-total "$MAX_EVENT_DLQ" \
  --metrics-out "$METRICS_OUT" \
  --pushgateway-url "$PUSHGATEWAY_URL" \
  --pushgateway-job "$PUSHGATEWAY_JOB"

ACTION="$(python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path('stress/canary_gate_decision.json').read_text(encoding='utf-8'))
print(data.get('action', 'rollback'))
PY
)"

if [ "$ACTION" = "promote" ]; then
  printf 'canary action: promote\n'
  exit 0
fi

python3 "$ROOT_DIR/platform/deploy/scripts/p3_5_autosafemode.py" \
  --decision "$ROOT_DIR/stress/canary_gate_decision.json" \
  --override-out "${P3_5_OVERRIDE_OUT:-$ROOT_DIR/platform/deploy/runtime-overrides.env}" \
  --incident-out "${P3_5_INCIDENT_OUT:-$ROOT_DIR/stress/p3_5_incident_ticket.json}"

printf 'canary action: rollback\n'
exit 2
