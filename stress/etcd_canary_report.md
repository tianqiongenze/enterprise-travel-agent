# Etcd Client Migration Canary Report

## 1. Comparison Summary

- Legacy mode: `legacy`
- New mode: `new`
- Consistency status: **pass**
- Fail reasons: none

## 2. Metric Table

| Metric | Legacy | New |
|---|---:|---:|
| success_rate | 0.0 | 0.0 |
| avg_latency_ms | 4.3 | 1.66 |
| p95_latency_ms | 12.32 | 2.01 |
| p99_latency_ms | 12.32 | 2.01 |
| missing_service_errors | 10 | 10 |
| missing_tool_errors | 10 | 10 |

## 3. Gate Decision

- ✅ Promote canary: consistency gate passed.
- Suggested actions:
  1. Verify service/tool catalog parity.
  2. Compare latency and error histogram drift.
  3. Re-run canary after fix before full rollout.
