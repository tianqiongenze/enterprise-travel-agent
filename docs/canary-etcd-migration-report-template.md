# Etcd Client Migration Canary Report Template

## 0. Context

- Date:
- Environment:
- Legacy version / deployment:
- New version / deployment:
- Evaluator:

---

## 1. Migration Scope

- Change target: etcd client dual-stack migration (`legacy` -> `new`)
- Runtime switch: `TRAVEL_ETCD_CLIENT_MODE=legacy|new|auto`
- Validation objective: service discovery and tool registry consistency under comparable load

---

## 2. Test Setup

- Legacy endpoint: `http://.../runtime/recommend`
- New endpoint: `http://.../runtime/recommend`
- Requests per mode:
- Concurrency:
- Timeout:
- Internal auth strategy: trace-id + internal signature

Command example:

```bash
python3 stress/etcd_migration_drill.py \
  --legacy-base-url http://legacy-host:8000 \
  --new-base-url http://new-host:8001 \
  --requests 300 \
  --concurrency 30 \
  --out-json stress/etcd_migration_compare.json \
  --out-md stress/etcd_canary_report.md
```

---

## 3. Comparison Summary

- Consistency status: PASS / FAIL
- Success-rate gap:
- Fail reasons:

Gate policy:

- PASS: no consistency mismatch and no critical drift
- FAIL: any critical mismatch (service/tool catalog mismatch, major error-rate delta)

---

## 4. Metric Table

| Metric | Legacy | New | Drift | Gate |
|---|---:|---:|---:|---|
| success_rate |  |  |  |  |
| avg_latency_ms |  |  |  |  |
| p95_latency_ms |  |  |  |  |
| p99_latency_ms |  |  |  |  |
| missing_service_errors |  |  |  |  |
| missing_tool_errors |  |  |  |  |

---

## 5. Consistency Checks

### 5.1 Service discovery

- `registered_agents` parity:
- Missing/extra entries:

### 5.2 Tool directory

- `registered_tools` parity:
- Missing/extra entries:

### 5.3 Error distribution

- HTTP status histogram comparison:
- Non-200 drift notes:

---

## 6. SLO & Release Gate Decision

- SLO thresholds:
  - Error rate <=
  - p95 <=
  - p99 <=
- Decision: Promote / Hold / Rollback
- Decision rationale:

---

## 7. Risks & Follow-ups

- Residual risks:
- Next actions:
- Owner + ETA:

---

## 8. Public-sharing Notes (课堂/公开分享)

- Demo highlights:
- Evidence artifacts:
  - JSON comparison: `stress/etcd_migration_compare.json`
  - Markdown report: `stress/etcd_canary_report.md`
- Key takeaway:
