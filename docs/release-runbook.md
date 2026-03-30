# Release Runbook (Full Stack)

## 0. Scope

This runbook covers release flow for:

- Python runtime API
- Spring gateway
- Web frontend (`frontend-web`)
- WeChat mini program (`miniapp-wechat`)

## 1. Pre-Release Commands

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
cd techgroup-enterprise-travel-gateway && mvn -B test
cd ../frontend-web && npm install --include=dev && npm run build
cd ..
python3 stress/etcd_migration_drill.py --legacy-base-url http://localhost:8000 --new-base-url http://localhost:8001 --requests 200 --concurrency 20
```

Required artifacts:

- `stress/etcd_migration_compare.json`
- `stress/etcd_canary_report.md`

P2 additional commands:

```bash
python3 scripts/run_event_consumers.py --max-messages 100
python3 stress/capacity_cost_model.py --peak-connected 1000000 --active-ratio 0.1
kustomize build --load-restrictor=LoadRestrictionsNone deploy/k8s/kustomize/overlays/region-a > /tmp/region-a.yaml
kustomize build --load-restrictor=LoadRestrictionsNone deploy/k8s/kustomize/overlays/region-b > /tmp/region-b.yaml
kustomize build --load-restrictor=LoadRestrictionsNone deploy/k8s/kustomize/overlays/region-c > /tmp/region-c.yaml
```

Required P2 artifacts:

- `stress/capacity_cost_report.json`
- `stress/capacity_cost_report.md`
- event pipeline outputs under `var/events/`

P3 resilience checks:

```bash
python3 scripts/run_event_consumers.py --max-messages 200 --max-retries 3 --retry-backoff-ms 200
cat stress/pulsar_consumer_metrics.prom
python3 deploy/scripts/canary_gate.py \
  --report stress/etcd_migration_compare.json \
  --event-metrics stress/pulsar_consumer_metrics.prom \
  --max-event-lag-seconds 60 \
  --max-event-dlq-total 0
```

Required P3 artifacts:

- `stress/pulsar_consumer_metrics.prom`
- `var/events/local_dlq_events.jsonl` or `var/events/pulsar_dlq_events.jsonl`
- screenshot/export of `grafana-dashboard-event-consumer.json`

P3.6 final checks:

```bash
python3 deploy/scripts/p3_5_autosafemode.py --decision stress/canary_gate_decision.json
curl -s http://localhost:8080/api/v1/travel/policy/cache/stats
```

Required P3.6 artifacts:

- `deploy/runtime-overrides.env` (when rollback with event reasons)
- `stress/p3_5_incident_ticket.json` (when rollback with event reasons)

Expansion verification commands:

```bash
export TRAVEL_ORCHESTRATION_ENGINE=langgraph
export TRAVEL_ORCHESTRATION_SHADOW_ENGINE=agentscope
export TRAVEL_ORCHESTRATION_FALLBACK_ENGINE=langgraph
export TRAVEL_ORCHESTRATION_STRICT=false
export TRAVEL_A2A_TRANSPORT=redis
export TRAVEL_A2A_REDIS_URL=redis://localhost:7000
export TRAVEL_A2A_STREAM_GROUP=a2a-consumers
export TRAVEL_A2A_PENDING_RETRY_IDLE_MS=10000
export TRAVEL_EVENT_CONSUMER_WORKERS=4
export TRAVEL_EVENT_CONSUMER_QUEUE_CAPACITY=512
export TRAVEL_A2A_AUDIT_MIRROR_PULSAR=true
export TRAVEL_A2A_AUDIT_TOPIC=persistent://public/default/travel-agent.a2a.audit
python3 -m unittest tests.test_orchestration_engine_modes -v
python3 -m unittest tests.test_agent_expansion tests.test_cache_manager -v
python3 deploy/scripts/export_a2a_stream_metrics.py
python3 stress/a2a_audit_replay_check.py --file var/events/a2a_audit_events.jsonl --window-minutes 60 --max-duplicates 0

# assets
# deploy/k8s/a2a-metrics-cronjob.yaml
# deploy/monitoring/grafana-dashboard-a2a-stream-pulsar.json

export TRAVEL_REDIS_MODE=cluster
export TRAVEL_REDIS_URL=redis://localhost:7000
python3 stress/redis_cluster_scenarios.py
```

Optional GraphRAG/Faiss verification:

```bash
pip install -r requirements-rag-optional.txt
export TRAVEL_VECTOR_BACKEND=faiss
python3 -m unittest tests.test_vector_backends -v
```

Harness replay quick check:

```bash
python3 - <<'PY'
from pathlib import Path
from src.travel_agent.models import TravelRequest
from src.travel_agent.orchestrator import build_orchestrator

project_root = str(Path.cwd())
orchestrator = build_orchestrator(project_root)
orchestrator.recommend(TravelRequest(city="北京", days=2, budget=3000, travelers=1, preferences=["family"]))
print(orchestrator.replay_last_harness_case())
PY
```

## 2. Deploy Sequence

Global multi-region deployment and failover details:

- `docs/global-active-active-deployment-plan.md`

1. Deploy runtime API
2. Deploy spring gateway
3. Deploy web frontend assets
4. Verify health endpoints
5. Gradually shift traffic

Health checks:

- `GET /health` (runtime)
- `GET /api/v1/travel/health` (gateway)

## 3. Canary Verification

Monitor for 15~30 minutes:

- success rate
- p95 / p99 latency
- 5xx error ratio
- registry consistency
- Pulsar publish/consume lag
- vector backend query health

Decision:

- Promote when all metrics within threshold
- Hold when mild drift appears
- Rollback when critical threshold breached

## 4. Rollback

Rollback order:

1. Web frontend (previous static bundle)
2. Gateway service
3. Runtime service

After rollback:

- rerun smoke tests
- freeze release window
- create incident notes with owner and ETA

## 5. WeChat Mini Program Release

1. Import `miniapp-wechat` into WeChat DevTools
2. Update API domain to production gateway domain
3. Build and upload test version
4. Complete platform review and gray release
5. Observe error/latency trends before full rollout
