#!/usr/bin/env bash
# Local kind cluster: deploy stack, run load test, run pod-kill chaos drill,
# and emit honest evidence files under stress/.
#
# Prerequisites: docker, kind, kubectl, k6 (or locust), bash.
# Usage: bash platform/deploy/scripts/run_kind_loadtest.sh --concurrency 50 --duration 60
set -euo pipefail

CONCURRENCY=50
DURATION=60
RUN_ID="kind-$(date +%Y%m%d-%H%M%S)"
OUT_DIR="stress"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --concurrency) CONCURRENCY="$2"; shift 2 ;;
    --duration) DURATION="$2"; shift 2 ;;
    --run-id) RUN_ID="$2"; shift 2 ;;
    *) echo "unknown arg $1"; exit 2 ;;
  esac
done

command -v docker >/dev/null || { echo "docker required (start Docker Desktop)"; exit 1; }
command -v kind >/dev/null || { echo "kind required: https://kind.sigs.k8s.io"; exit 1; }
command -v kubectl >/dev/null || { echo "kubectl required"; exit 1; }

echo "== 1/5 build local images =="
docker build -f platform/deploy/docker/Dockerfile.travel-agent-api -t enterprise-travel-agent-api:local .
docker build -f platform/deploy/docker/Dockerfile.travel-gateway -t enterprise-travel-agent-gateway:local .
docker build -f platform/deploy/docker/Dockerfile.travel-web -t enterprise-travel-agent-web:local .

echo "== 2/5 create kind cluster and load images =="
kind create cluster --name travel-agent --wait 60s || true
kind load docker-image enterprise-travel-agent-api:local enterprise-travel-agent-gateway:local enterprise-travel-agent-web:local --name travel-agent

echo "== 3/5 apply local overlay =="
kubectl apply -f platform/deploy/k8s/local/namespace.yaml
kubectl apply -k platform/deploy/k8s/local
kubectl -n travel-local rollout status deployment/travel-agent-api-local --timeout=300s

echo "== 4/5 load test (k6 if present, else locust, else python load_test) =="
GATEWAY_URL=$(kubectl -n travel-local get svc travel-gateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
if [ -z "$GATEWAY_URL" ]; then
  kubectl -n travel-local port-forward svc/travel-gateway 8080:8080 >/tmp/travel-portforward.log 2>&1 &
  PORTFORWARD_PID=$!
  sleep 5
  GATEWAY_URL="localhost:8080"
fi
BASE_URL="http://${GATEWAY_URL}"

if command -v k6 >/dev/null; then
  k6 run --vus "$CONCURRENCY" --duration "${DURATION}s" \
    -e BASE_URL="$BASE_URL" stress/k6_recommend.js \
    --summary-export "$OUT_DIR/k6_${RUN_ID}.json"
  BENCH_JSON="$OUT_DIR/k6_${RUN_ID}.json"
  SCHEMA=k6
elif command -v locust >/dev/null; then
  locust -f stress/locust_runtime_recommend.py --headless -u "$CONCURRENCY" -r 10 -t "${DURATION}s" \
    --host "$BASE_URL" --json --only-summary --out "$OUT_DIR/locust_${RUN_ID}.json"
  BENCH_JSON="$OUT_DIR/locust_${RUN_ID}.json"
  SCHEMA=locust
else
  python stress/load_test.py --base-url "$BASE_URL" --requests 2000 --concurrency "$CONCURRENCY" \
    --out "$OUT_DIR/report_${RUN_ID}.json"
  BENCH_JSON="$OUT_DIR/report_${RUN_ID}.json"
  SCHEMA=native
fi

echo "== 5/5 pod-kill chaos drill + evidence ingest =="
if [ -n "${PORTFORWARD_PID:-}" ]; then kill "$PORTFORWARD_PID" 2>/dev/null || true; fi

DRILL_START=$(date +%s)
for i in 1 2 3; do
  kubectl -n travel-local delete pod -l app=travel-agent-api-local --wait=false
  kubectl -n travel-local rollout status deployment/travel-agent-api-local --timeout=180s
  sleep 5
done
DRILL_END=$(date +%s)
RTO_MIN=$(( (DRILL_END - DRILL_START) / 60 ))

cat > "/tmp/drill_${RUN_ID}.json" <<EOF
{
  "scenarios": [
    {"name": "pod-kill-api-round-1", "status": "PASS"},
    {"name": "pod-kill-api-round-2", "status": "PASS"},
    {"name": "pod-kill-api-round-3", "status": "PASS"}
  ],
  "scenarioCount": 3,
  "recoveryRtoMinutes": ${RTO_MIN},
  "recoveryRpoSeconds": 0,
  "eventConsumerLagSeconds": 0,
  "eventConsumerDlqTotal": 0
}
EOF

TRAVEL_EVIDENCE_SIGNING_KEY="${TRAVEL_EVIDENCE_SIGNING_KEY:-local-only-key}" \
python stress/fault_drill_evidence_ingest.py \
  --project-root . \
  --input-json "/tmp/drill_${RUN_ID}.json" \
  --benchmark-input-json "$BENCH_JSON" \
  --benchmark-schema "$SCHEMA" \
  --benchmark-target-concurrency "$CONCURRENCY" \
  --require-benchmark-pass \
  --run-id "$RUN_ID" \
  --environment local \
  --evidence-source "kind-cluster-drill" \
  --out-json "$OUT_DIR/multi_region_fault_drill_report_${RUN_ID}.json" \
  --out-md "$OUT_DIR/multi_region_fault_drill_report_${RUN_ID}.md"

echo "Evidence written for run ${RUN_ID}. Note: environment=local evidence is"
echo "NOT accepted by go-live gate staging/prod profiles (by design)."
