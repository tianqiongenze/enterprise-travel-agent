#!/usr/bin/env bash
# Chaos drill: ranker pod kill + recovery, registry-cache scale-to-zero degrade,
# runtime rolling restart. Requires a reachable kubectl cluster; otherwise
# writes a SKIPPED evidence report and exits 0.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
STRESS_DIR="$ROOT/stress"
mkdir -p "$STRESS_DIR"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
NAMESPACE="${CHAOS_NAMESPACE:-travel}"
SHA="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"

JSON="$STRESS_DIR/chaos_drill_report.json"
MD="$STRESS_DIR/chaos_drill_report.md"
SCENARIOS_JSON="["
SCENARIOS_MD=""
OVERALL="PASS"

append_scenario() {
  local name="$1" status="$2" detail="$3" recovery="$4"
  if [ "$SCENARIOS_JSON" != "[" ]; then SCENARIOS_JSON="$SCENARIOS_JSON,"; fi
  SCENARIOS_JSON="$SCENARIOS_JSON{\"name\":\"$name\",\"status\":\"$status\",\"detail\":\"$detail\",\"recoverySeconds\":$recovery}"
  SCENARIOS_MD="$SCENARIOS_MD
- **$name**: $status — $detail (recovery: ${recovery}s)"
  if [ "$status" = "FAIL" ]; then OVERALL="FAIL"; fi
}

if ! command -v kubectl >/dev/null 2>&1; then
  append_scenario "cluster-prerequisite" "SKIPPED" "kubectl not found on PATH; no cluster to drill" "0"
  SCENARIOS_JSON="$SCENARIOS_JSON]"
  OVERALL="SKIPPED"
else
  if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
    append_scenario "cluster-prerequisite" "SKIPPED" "namespace $NAMESPACE unreachable via kubectl" "0"
    SCENARIOS_JSON="$SCENARIOS_JSON]"
    OVERALL="SKIPPED"
  else
    SCENARIOS_JSON="$SCENARIOS_JSON]"

    # Scenario 1: kill ranker pods, time recovery
    START=$(date +%s)
    KILLED=$(kubectl get pods -n "$NAMESPACE" -l app=travel-ranker-go -o name 2>/dev/null | wc -l)
    if [ "$KILLED" -eq 0 ]; then
      append_scenario "ranker-pod-kill" "SKIPPED" "no travel-ranker-go pods found in $NAMESPACE" "0"
    else
      kubectl delete pod -n "$NAMESPACE" -l app=travel-ranker-go --force --grace-period=0 >/dev/null 2>&1
      for _ in $(seq 1 60); do
        READY=$(kubectl get pods -n "$NAMESPACE" -l app=travel-ranker-go -o jsonpath='{.items[*].status.containerStatuses[*].ready}' 2>/dev/null | grep -c true)
        if [ "$READY" -ge "$KILLED" ]; then break; fi
        sleep 2
      done
      END=$(date +%s)
      RECOVERY=$((END - START))
      if [ "$READY" -ge "$KILLED" ]; then
        append_scenario "ranker-pod-kill" "PASS" "$KILLED ranker pods killed and recovered" "$RECOVERY"
      else
        append_scenario "ranker-pod-kill" "FAIL" "$KILLED pods killed, only $READY ready after 120s" "120"
      fi
    fi

    # Scenario 2: scale registry-cache to zero and back
    kubectl scale deployment travel-registry-cache-go -n "$NAMESPACE" --replicas=0 >/dev/null 2>&1
    if [ $? -ne 0 ]; then
      append_scenario "registry-cache-scale-zero" "SKIPPED" "deployment travel-registry-cache-go not found" "0"
    else
      sleep 3
      ZERO=$(kubectl get deployment travel-registry-cache-go -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null)
      kubectl scale deployment travel-registry-cache-go -n "$NAMESPACE" --replicas=1 >/dev/null 2>&1
      START=$(date +%s)
      for _ in $(seq 1 60); do
        READY=$(kubectl get deployment travel-registry-cache-go -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
        if [ "$READY" = "1" ]; then break; fi
        sleep 2
      done
      END=$(date +%s)
      RECOVERY=$((END - START))
      if [ "$ZERO" = "0" ] && [ "$READY" = "1" ]; then
        append_scenario "registry-cache-scale-zero" "PASS" "scaled to 0 then back to 1 ready replica" "$RECOVERY"
      else
        append_scenario "registry-cache-scale-zero" "FAIL" "scale-to-zero=$ZERO, ready=$READY after wait" "$RECOVERY"
      fi
    fi

    # Scenario 3: runtime rolling restart
    START=$(date +%s)
    kubectl rollout restart deployment travel-runtime -n "$NAMESPACE" >/dev/null 2>&1
    if [ $? -ne 0 ]; then
      append_scenario "runtime-rolling-restart" "SKIPPED" "deployment travel-runtime not found" "0"
    else
      if kubectl rollout status deployment travel-runtime -n "$NAMESPACE" --timeout=180s >/dev/null 2>&1; then
        END=$(date +%s)
        append_scenario "runtime-rolling-restart" "PASS" "rollout completed" "$((END - START))"
      else
        END=$(date +%s)
        append_scenario "runtime-rolling-restart" "FAIL" "rollout did not complete within 180s" "$((END - START))"
      fi
    fi
  fi
fi

if [ "$SCENARIOS_JSON" = "[" ]; then SCENARIOS_JSON="[]"; fi

cat > "$JSON" <<EOF
{
  "timestamp": "$TS",
  "gitSha": "$SHA",
  "overall": "$OVERALL",
  "scenarios": $SCENARIOS_JSON
}
EOF

cat > "$MD" <<EOF
# Chaos Drill Report

- Timestamp: $TS
- Git SHA: $SHA
- Overall: **$OVERALL**

## Scenarios
$SCENARIOS_MD
EOF

echo "chaos drill: overall=$OVERALL report=$JSON"
exit 0
