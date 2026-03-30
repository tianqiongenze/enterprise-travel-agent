# Global Active-Active Deployment Reference

## Topology

- Region A / Region B / Region C
- Each region contains:
  - `techgroup-enterprise-travel-gateway` deployment
  - `travel-agent-api` deployment
  - Go service deployments (`go-fanout`, `go-ranker`, `go-policy`, `go-registry-cache`)
  - regional cache and vector index

## Traffic Strategy

- Global traffic entry: Anycast + GeoDNS.
- Regional fallback order: local -> nearest -> global backup.
- Canary rollout by region, never global all-at-once.

## Data & Messaging

- Pulsar: enable geo-replication topics for cross-region event propagation.
- Vector DB:
  - Qdrant: shard by tenant/region, replicate hot partitions.
  - Milvus: partition by region and business domain.
- OLTP DB: avoid blind multi-master; use ownership-based write routing.

## SRE Controls

- Mandatory release gates:
  - `canary_gate_status == 1`
  - no critical alerts
  - p95/p99 in SLO window
- Region-level rollback scripts must be tested every sprint.

## Minimal Env Baseline

- `TRAVEL_EVENT_BUS=pulsar`
- `PULSAR_SERVICE_URL=pulsar://pulsar-broker:6650`
- `TRAVEL_MEMORY_BACKEND=vector`
- `TRAVEL_VECTOR_BACKEND=qdrant` (or `milvus`)
- `TRAVEL_VECTOR_STRICT=true`

