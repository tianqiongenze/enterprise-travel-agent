# Go-Live Checklist (Backend + Web + Mini Program)

## 1. Environments

- [ ] Dev / Staging / Prod environment variables separated
- [ ] `TRAVEL_RUNTIME_BASE_URL` configured by environment
- [ ] `VITE_TRAVEL_API_BASE_URL` points to gateway domain
- [ ] Mini program legal request domains configured

## 2. Security Gates

- [ ] Shared secret and internal client id rotated from defaults
- [ ] TLS certificate enabled on ingress/domain
- [ ] CORS whitelist configured (no wildcard in production)
- [ ] Security headers enabled on Nginx ingress

## 3. Quality Gates

- [ ] Python tests pass
- [ ] Spring gateway tests pass
- [ ] Web frontend build passes
- [ ] Miniapp structure check passes in CI
- [ ] Etcd migration drill report generated and attached

## 4. Performance and Reliability

- [ ] Baseline load test report attached
- [ ] Canary report decision recorded (Promote / Hold / Rollback)
- [ ] Rollback command/script verified in staging
- [ ] Error budget/SLO dashboard available

## 5. Observability and Operations

- [ ] Trace ID visible across gateway and runtime logs
- [ ] Alert rules for 5xx rate and latency p95/p99 active
- [ ] On-call owner and escalation contacts documented
- [ ] Runbook links provided to release manager

## 6. P2 Enterprise Gates (Global / MQ / Vector)

- [ ] Pulsar event bus enabled (`TRAVEL_EVENT_BUS=pulsar`) and consumer pipeline running
- [ ] Consumer evidence exists (`audit_events.jsonl`, `profile_updates.jsonl`, `notifications.jsonl`)
- [ ] Vector backend selected (`qdrant` or `milvus`) with strict mode validated in staging
- [ ] Region overlays build successfully (`region-a`, `region-b`, `region-c`)
- [ ] Capacity/cost report generated (`stress/capacity_cost_report.json` and `.md`)
- [ ] Canary + rollback decision includes MQ/vector health signals

## 7. Final Release Decision

- [ ] Product signoff
- [ ] Engineering signoff
- [ ] Security signoff
- [ ] Release manager signoff

## 8. P3 Resilience Gates

- [ ] Event retry policy validated in staging (`max_retries`, `backoff_ms`)
- [ ] DLQ route verified (topic/file output) and alert linked
- [ ] Consumer metrics file exported (`stress/pulsar_consumer_metrics.prom`)
- [ ] Prometheus alerts for consumer lag/DLQ/failure tested
- [ ] Grafana event-consumer dashboard imported and reviewed

## 9. P3.6 Final Gates

- [ ] Auto-safemode script validated (`deploy/scripts/p3_5_autosafemode.py`)
- [ ] Runtime override artifact path validated (`deploy/runtime-overrides.env`)
- [ ] Incident ticket artifact generated on rollback (`stress/p3_5_incident_ticket.json`)
- [ ] Java policy cache stats endpoint validated (`/api/v1/travel/policy/cache/stats`)
- [ ] Final release evidence package archived with canary gate decision

## 10. Expansion Gates (Agent + Orchestration + Redis Cluster)

- [ ] New agents enabled (`food/local-event/loyalty-growth/weather-risk/ancillary-revenue/visa-compliance/concierge`) and output verified
- [ ] New MCP tools enabled (`search_foods`, `search_events`) and audited
- [ ] Orchestration engine mode selected and validated (`local|langgraph|agentscope|oneagents`)
- [ ] Orchestration fallback validated (`TRAVEL_ORCHESTRATION_FALLBACK_ENGINE`, `TRAVEL_ORCHESTRATION_STRICT`)
- [ ] Harness replay verified (`replay_last_harness_case`) with latest sample
- [ ] Redis Cluster mode validated (`TRAVEL_REDIS_MODE=cluster`, `TRAVEL_REDIS_URL`)
- [ ] Redis scenarios verified (rate limit, idempotency, lock, profile, itinerary, popularity, recent-search)
- [ ] A2A distributed transport validated (`TRAVEL_A2A_TRANSPORT=redis`) with stream pending retry checks
- [ ] A2A Pulsar audit mirror validated (`TRAVEL_A2A_AUDIT_MIRROR_PULSAR=true`)
- [ ] A2A metrics CronJob deployed (`deploy/k8s/a2a-metrics-cronjob.yaml`)
- [ ] Grafana tri-view imported (`deploy/monitoring/grafana-dashboard-a2a-stream-pulsar.json`)
- [ ] Membership distributed store enabled (`TRAVEL_MEMBERSHIP_REDIS_URL`)
- [ ] Runtime anti-abuse gates enabled (rate-limit/idempotency/circuit)

## 11. 10B / 1M Global Capacity Gates

- [ ] `stress/global_scale_readiness_report.json` generated and archived
- [ ] Readiness status is at least `ARCHITECTURE_READY_NOT_PROVEN`
- [ ] Distributed benchmark evidence attached for `>= 1,000,000` concurrent users
- [ ] Multi-region active-active failover drill evidence attached
- [ ] Runtime in-flight admission control enabled (`TRAVEL_INFLIGHT_LIMIT`)
- [ ] Go Ranker gRPC transport and fallback metrics exported (`stress/ranker_transport_metrics.prom`)
- [ ] Distributed benchmark evidence generated (`stress/distributed_benchmark_evidence.json`)
- [ ] Multi-region fault drill evidence generated (`stress/multi_region_fault_drill_report.json`)
- [ ] Final gate passes with `--min-scale-status PRODUCTION_PROVEN`

## 12. Data Flywheel / Lakehouse Gates

- [ ] Data flywheel pipeline manifest exists (`var/lakehouse/flywheel_manifest.json`)
- [ ] Bronze/Silver/Gold artifacts generated under `var/lakehouse/`
- [ ] Flink + Iceberg design reviewed (`docs/data-flywheel-lakehouse-design.md`)

