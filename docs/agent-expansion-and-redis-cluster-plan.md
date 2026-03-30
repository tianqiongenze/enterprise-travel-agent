# Agent Expansion + Redis Cluster Evolution Plan

## 1. Why expand agent types now

Current platform already supports core travel recommendation. Next value layer is business stickiness and lifecycle growth.

New agent categories introduced in this phase:

1. `food-recommendation-agent` (餐饮推荐)
2. `local-event-agent` (本地活动)
3. `loyalty-growth-agent` (增长运营建议)
4. `weather-risk-agent` (天气风险与行程兜底)
5. `ancillary-revenue-agent` (增购与附加营收)
6. `visa-compliance-agent` (签证与跨境合规)
7. `concierge-agent` (高等级会员专属服务)

Expected business impact:

- More cross-sell opportunities (food/events)
- Better retention through loyalty actions
- More complete itinerary experience

## 2. Why Nacos + Etcd together

- Nacos is strong for enterprise service governance and operational console.
- Etcd is strong for consistency and cloud-native control-plane style workflows.
- Dual stack enables migration safety (`legacy/new/auto`) and rollback isolation.

## 3. Why Redis + RocksDB together

- Redis Cluster: shared hot cache, rate limit, idempotency, distributed lock, profile cache.
- RocksDB: local persistent high-throughput storage for node-local scenarios.
- Combined strategy balances low latency, durability, and cost.

## 4. Why Kafka path upgraded to Pulsar

- Pulsar provides multi-tenancy, storage/compute separation, and geo-replication friendliness.
- Better fit for cross-region active-active and event fanout at scale.
- Current implementation defaults to Pulsar with local fallback for developer mode.

## 5. Why active-active and global deployment

- Near-region access reduces latency.
- Region-level fault isolation improves SLA and resilience.
- Better compliance partitioning and scaling envelope.

## 6. Framework evolution path (A2A/MCP/Skills/Harness)

Current phase provides a pluggable orchestration engine adapter:

- `langgraph` (default adapter)
- `agentscope` adapter
- `oneagents` adapter

Selection via env:

- `TRAVEL_ORCHESTRATION_ENGINE=local|langgraph|agentscope|oneagents`

Notes:

- `local/native` orchestration now routes to configurable framework fallback (`TRAVEL_ORCHESTRATION_FALLBACK_ENGINE`).
- Optional dependencies in `requirements-orchestration-optional.txt`.
- Added lightweight Harness replay (`src/travel_agent/harness/replay.py`) to capture and replay orchestration cases.
- GraphRAG hints integrated in itinerary ranking (`src/travel_agent/memory/graphrag.py`).
- Faiss backend available via `requirements-rag-optional.txt` and `TRAVEL_VECTOR_BACKEND=faiss`.
- A2A transport upgraded to distributed Redis channel (`TRAVEL_A2A_TRANSPORT=redis`).

## 7. Redis Cluster usage scenarios implemented

- Hot destination plan cache (`hot_plan:*`)
- User rate limiting (`rate_limit:user:*`)
- Idempotency replay guard (`idempotency:*`)
- Distributed lock (`lock:*`)
- User profile cache (`profile:*`)
- Itinerary snapshot cache (`itinerary:*`)
- City popularity counter (`city_popularity:*`)
- Recent search history (`recent_search:*`)

Scenario script:

```bash
python stress/redis_cluster_scenarios.py
```

## 8. Delivery checklist

- [x] New agents registered and exposed
- [x] New MCP tools (`search_foods`, `search_events`)
- [x] Orchestration engine adapter support
- [x] Redis Cluster memory and cache manager support
- [x] Docker Compose Redis Cluster service
- [x] Unit tests for expansion and engine mode
- [x] Harness replay and cache scenario unit tests
- [x] Documentation updates

