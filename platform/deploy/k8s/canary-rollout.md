# Canary Rollout Strategy

## Steps

1. Deploy 5% traffic canary for new version
2. Observe 30 minutes: error rate, p95/p99, saturation
3. If healthy, ramp to 25% -> 50% -> 100%
4. If SLO breach, rollback automatically

## Rollback triggers

- error rate > 1%
- p99 increase > 50% vs baseline
- repeated 5xx bursts over 5 minutes

## Required dashboards

- gateway latency/error
- runtime latency/error
- MCP tool timeout histogram
- registry heartbeat/lease failure counters
