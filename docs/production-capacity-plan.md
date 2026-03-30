# Production Capacity Plan (Enterprise)

## 1. Reality Check for 1M Concurrent / 100M Users

This project now includes production integration paths, but **a local test cannot prove 1M concurrent realtime or 100M user scale**.

What we can prove locally:

- single-node throughput and latency envelope
- error behavior under burst concurrency
- registry integration correctness (Nacos/Etcd path)

What must be proven in distributed staging:

- long-lived 1M connection behavior
- cross-zone load balancer, reconnect storms, autoscaling dynamics
- sustained p99 and saturation points with real downstream dependencies

## 2. Recommended production stack

- Spring Gateway cluster (Boot 3.5.12 + Spring AI 1.1.3 + Spring AI Alibaba 1.1.2.2)
- Python runtime cluster with MCP tools and Skills
- Registry center: Nacos or Etcd cluster (HA)
- Redis/RocksDB memory tier + message queue + observability stack

## 2.1 Memory backend strategy

- Default: `memory` for dev/demo simplicity
- Production short-term memory: `redis` (shared, TTL)
- Production durable memory: `rocksdb` (node-local persistent)
- Semantic retrieval layer: `vector` (query augmentation)

Important: explicit backend selection is strict; missing dependencies/config should fail fast.

## 2.2 Etcd client migration (dual-stack)

- Runtime switch: `TRAVEL_ETCD_CLIENT_MODE=legacy|new|auto`
- Packaging split: `requirements-etcd-legacy.txt` and `requirements-etcd-new.txt`
- Rollout strategy: canary with new client, compare registry correctness and latency, then promote

## 3. Capacity formula (baseline)

- `instances_gateway ~= peak_connected / conn_per_instance * safety_factor`
- `instances_runtime ~= peak_active_ai / active_slots_per_instance * safety_factor`
- Safety factor recommended: 1.5~2.0

### 3.1 Example sizing envelope for 1M concurrent sessions

Use this only as a planning starting point, not as final evidence:

- Peak connected sessions: `1,000,000`
- Active ratio at peak (simultaneous AI generation): `8% ~ 15%`
- Gateway steady connection capacity target per pod: `8,000 ~ 15,000`
- Runtime active slots per pod (LLM + tools + memory): `60 ~ 150`
- Safety factor: `1.8`

Illustrative range:

- Gateway pods: `1,000,000 / 15,000 * 1.8 ≈ 120` (optimistic) to
  `1,000,000 / 8,000 * 1.8 ≈ 225` (conservative)
- Runtime pods (assuming 10% active = 100,000 active requests):
  `100,000 / 150 * 1.8 ≈ 1,200` to `100,000 / 60 * 1.8 ≈ 3,000`

Interpretation:

- 1M concurrency is a **cluster architecture objective**, not a single-service benchmark target.
- Gateway connection handling and runtime active generation scale are separate bottlenecks and must be independently budgeted.

### 3.2 Throughput and dependency budget guardrails

- Define per-request dependency fanout budget (registry/memory/tooling) before peak test.
- For each critical dependency, enforce p99 and error budget at 2x expected peak QPS.
- Require explicit backpressure strategy (queue, shed, degrade) when runtime saturation >85%.

## 4. Go-live checklist

- [ ] Multi-node distributed benchmark completed
- [ ] reconnect storm drill completed
- [ ] p95/p99 under SLO in canary traffic
- [ ] tool quotas and fallback policies validated
- [ ] incident runbook and kill-switch tested
- [ ] PrometheusRule imported and firing tests executed
- [ ] Grafana dashboard imported and on-call panel links verified
- [ ] Canary gate metrics present (`canary_gate_status`, drift, thresholds, timestamp)
- [ ] Staleness alert validated (`CanaryGateMetricsStale`)

## 4.1 Release gates (must-pass)

P0 (hard gate):

1. `canary_gate_status == 1` for the release candidate window
2. No active critical alerts:
   - `GroupcachePeerRefreshStale`
   - `CanaryGateRollbackDecision`
   - `CanaryGateSuccessGapExceeded`
3. Error budget burn rate within policy window (e.g., 1h and 6h)

P1 (warning gate, requires explicit sign-off):

1. `GroupcachePeersTooLow`
2. `GroupcachePeerRefreshErrorsIncreasing`
3. `CanaryGateP95DriftExceeded` / `CanaryGateP99DriftExceeded`

If any P0 gate fails, block promotion and trigger rollback workflow.

## 5. Local stress baseline (this project)

### Scenario A

- Requests: 1000
- Concurrency: 100
- Success rate: 100%
- Avg latency: 147.95 ms
- p95: 172.05 ms
- p99: 184.86 ms

### Scenario B

- Requests: 5000
- Concurrency: 300
- Success rate: 100%
- Avg latency: 459.11 ms
- p95: 509.32 ms
- p99: 521.44 ms

Interpretation:

- API logic and concurrency control are stable under local burst conditions.
- These are **single-node** results and cannot be used alone as evidence for 1M concurrent/100M users claims.

## 6. Enterprise claim policy

To claim "1M concurrent realtime / 100M users", the following evidence package is mandatory:

1. Distributed load reports (multi-node generator + full chain metrics)
2. Canary rollout reports from production-like environment
3. SLO compliance evidence over sustained windows
4. Incident drill evidence (dependency outage / reconnect storm)

Without these, the correct statement is: "architecture supports scale-out and passed local/staging baselines".

## 7. Monitoring and dashboard assets for this repo

- Alert rules: `deploy/monitoring/prometheus-rule.yaml`
- Dashboard JSON: `deploy/monitoring/grafana-dashboard-go-runtime.json`
- Canary metric emission:
  - Script: `deploy/scripts/canary_gate.py`
  - Wrapper: `deploy/scripts/canary_promote_or_rollback.sh`
  - Output file: `stress/canary_gate_metrics.prom`

Recommended operational pattern:

1. Run canary gate script after each canary test window.
2. Publish/collect the generated metrics (file scrape or Pushgateway).
3. Evaluate PrometheusRule alert state before promotion.
4. Keep dashboard snapshots in release artifacts for auditability.

## 8. Industrial Upgrade for 10B Users / 10M Concurrent

### 8.1 Global capacity envelope

- Total connected sessions: `10,000,000`
- Peak active generation ratio: `8% ~ 15%`
- Peak active requests: `800,000 ~ 1,500,000`
- Safety factor baseline: `2.0`

Sizing assumptions:

- Gateway capacity per pod: `12,000` websocket/http long-lived sessions
- Runtime active slots per pod: `120`

Estimated baseline:

- Gateway pods: `10,000,000 / 12,000 * 2.0 ~= 1,667`
- Runtime pods at 1,000,000 active requests: `1,000,000 / 120 * 2.0 ~= 16,667`

### 8.2 Core architecture upgrades

1. Split ingress, gateway, orchestration runtime, and tool adapters into independent scaling domains.
2. Implement tenant-tier QoS with admission control and dynamic quotas.
3. Introduce adaptive concurrency limits with queue depth and timeout-aware shedding.
4. Keep cache and MQ by-region, by-tenant partitions with hot-key detection and isolation.
5. Enforce idempotency and replay-safe consumers for every at-least-once path.

### 8.3 Validation and testing matrix

- Unit + contract tests on every commit (blocking).
- Daily component stress tests (gateway/runtime/cache/mq).
- Weekly distributed peak simulation with fault injection.
- Pre-release sustained test (>= 12h) with production-like dependencies.
- Monthly resilience drill: regional outage + cache split-brain + MQ lag storm.

### 8.4 Deployment and release controls

- Mandatory canary + shadow evaluation before promotion.
- Promotion blocked if any P0 alert or SLO breach is active.
- Automatic rollback if burn rate exceeds policy window.
- Release artifact must include: load report, SLO report, rollback validation, and dashboard snapshots.

