# Global Active-Active Deployment and Failover Plan

## 1. Target Topology

Deploy three regions and keep all regions active:

- Region A (APAC primary user base)
- Region B (EMEA)
- Region C (Americas)

Each region contains the same logical stack:

- Ingress + WAF + API Gateway (`techgroup-enterprise-travel-gateway`)
- Runtime (`travel-agent-api`)
- Redis Cluster (regional write/read, TTL cache)
- Pulsar broker/proxy (regional message endpoint)
- Nacos + Etcd clients for service discovery and coordination
- Vector backend (Qdrant/Milvus/Faiss-sidecar strategy)
- Observability (Prometheus + Grafana + Alertmanager + logs)

Global shared services:

- Global DNS/GSLB (latency + health + weighted routing)
- Pulsar geo-replication between regions
- Object storage for immutable artifacts and reports

## 2. Component Deployment Matrix

| Component | Region Scope | Multi-Active Mode | Data Strategy |
|---|---|---|---|
| `techgroup-enterprise-travel-gateway` | all regions | active-active | stateless |
| `travel-agent-api` | all regions | active-active | stateless + external state |
| Redis Cluster | per region | active-active by partition | regional cache + TTL |
| Pulsar | per region + geo-replication | active-active | topic replication |
| Nacos | per region | active-active (local control plane) | local registry + sync metadata |
| Etcd | per region | active-active by control domain | local quorum |
| Vector backend | per region | active-active | tenant partition + async replication |

## 3. Traffic and Tenant Routing

- Use DNS policy: latency first, then health fallback.
- Use tenant pinning for sticky region assignment.
- For premium tenants, keep warm standby region pre-provisioned.
- Keep `X-Trace-Id` and tenant identity propagated end-to-end.

## 4. A2A and Event Strategy

- A2A command path: Redis Streams with consumer groups.
- A2A audit mirror: optional Pulsar mirror topic.
- Event pipeline: Pulsar as durable fanout and replay channel.
- Idempotency keys are required for at-least-once delivery tolerance.

Recommended environment settings:

```bash
TRAVEL_A2A_TRANSPORT=redis
TRAVEL_A2A_REDIS_URL=redis://redis-cluster:7000
TRAVEL_A2A_AUDIT_MIRROR_PULSAR=true
TRAVEL_A2A_AUDIT_TOPIC=persistent://public/default/travel-agent.a2a.audit
TRAVEL_EVENT_BUS=pulsar
PULSAR_SERVICE_URL=pulsar://pulsar:6650
```

## 5. Multi-Region Data Consistency Model

- Cache and session-like data: eventual consistency (Redis TTL).
- Policy and registration metadata: strong consistency inside a region, async cross-region sync.
- Event and audit: durable log with replay (Pulsar).
- Recommendation requests: idempotent by `idempotencyKey`.

## 6. Failure Scenarios and Automatic Switching

### 6.1 Region-level outage

1. GSLB marks region unhealthy.
2. Traffic is shifted to nearest healthy region.
3. Gateway validates policy locally and continues service.
4. Runtime uses fallback orchestration engine if needed.

### 6.2 Redis regional degradation

1. A2A read/write error rate crosses threshold.
2. Switch command path to fallback region endpoint or degrade to minimal flow.
3. Keep audit mirror on Pulsar to avoid data loss.

### 6.3 Pulsar degradation

1. Event bus write failure triggers alert.
2. Runtime uses local event fallback while preserving critical request path.
3. Replay missed windows once Pulsar recovers.

### 6.4 Vector backend degradation

1. Query timeout/error exceeds SLO.
2. Fallback to local vector backend.
3. Trigger background re-sync and capacity scale-out.

## 7. Rollback Plan (Production)

### 7.1 Application rollback

1. Freeze canary promotion.
2. Roll gateway deployment back first.
3. Roll runtime deployment back next.
4. Keep policy and data planes unchanged unless root cause requires.

### 7.2 Policy rollback

1. Set `TRAVEL_POLICY_BACKEND=java` (disable go-policy canary).
2. Keep shadow logging on for divergence diagnostics.
3. Re-run policy contract tests.

### 7.3 Orchestration rollback

1. Keep `TRAVEL_ORCHESTRATION_ENGINE` unchanged if healthy.
2. If engine-specific regression exists, switch to fallback engine via:

```bash
TRAVEL_ORCHESTRATION_ENGINE=local
TRAVEL_ORCHESTRATION_FALLBACK_ENGINE=langgraph
TRAVEL_ORCHESTRATION_STRICT=false
```

3. Validate `recommend.engine_selected` event and golden-request outputs.

### 7.4 A2A rollback

1. Keep Redis Streams transport as primary.
2. Disable Pulsar audit mirror if mirror path is unstable:

```bash
TRAVEL_A2A_AUDIT_MIRROR_PULSAR=false
```

3. Keep local audit JSONL as temporary evidence backup.

## 8. Cutover / Failback Runbook Checklist

- [ ] Global DNS health checks green in all target regions
- [ ] Policy backend mode validated (`java/go/canary`)
- [ ] Orchestration selected engine and fallback engine verified
- [ ] A2A Streams consume lag within threshold
- [ ] Pulsar mirror topic receive rate normal
- [ ] Key SLOs stable for 30+ minutes before full cutover
- [ ] Rollback command tested in staging in last 7 days

## 9. Capacity and SLO Baseline

Suggested baseline thresholds:

- API p95 < 300 ms
- API p99 < 700 ms
- Error rate < 0.5%
- A2A stream pending idle < 10 s
- Pulsar consumer lag < 60 s

Use existing scripts and reports:

- `stress/load_test.py`
- `stress/canary_gate_metrics.prom`
- `stress/go_live_final_report.json`

## 10. Upgrade Plan for 10B Users / 10M Concurrent

### 10.1 Regional topology target

- Minimum 3 active regions with independent control planes.
- Recommended 5-region global mesh for premium tenants.
- Tenant home-region pinning + policy-aware cross-region spillover.

### 10.2 Data-plane scaling strategy

- Gateway: stateless, globally anycast ingress, L7 retry budgets.
- Runtime: tenant-tier pools with adaptive concurrency and queue protection.
- Redis: multi-cluster shards partitioned by tenant hash + region.
- Pulsar: geo-replicated topics with strict retention tiers for audit.
- Vector backend: regional shards + async replica rebuild pipelines.

### 10.3 Control-plane and governance

- Unified policy-core release train across Java/Python/Go.
- Canary and shadow routing controlled by policy service.
- Centralized config rollout with immutable version tags.

### 10.4 Industrial deployment sequence

1. Build baseline in one region with full observability and replay.
2. Expand to three regions and validate failover RTO/RPO objectives.
3. Enable global traffic engineering with weighted policy-aware routing.
4. Introduce automated capacity planner and predictive pre-scale.

### 10.5 Mandatory release gates for global promotion

- All critical services at SLO for >= 60 minutes under canary load.
- Cross-region replay lag within budget.
- Region failover drill passed in last 14 days.
- Rollback completion time verified under 10 minutes.

