# Go Expansion Guide (Fanout, Policy, Registry Cache)

## 1) Fanout Service (go-fanout)

Purpose: concurrent dispatch and aggregation for stress/fanout tasks.

Endpoints:

- `POST /v1/fanout/dispatch`
  - request: `{ id, targets: [{name,url,method}], payload, timeoutMs }`
  - response: per-target status and latency

Use cases:

- replace ThreadPoolExecutor fanout in `stress/*.py`
- shadow-dispatch for dry-run target planning

Resilience stack:

- `errgroup` for structured parallel fanout
- `singleflight` for duplicate suppression
- `gobreaker` for per-target circuit break

## 2) Policy Runtime (go-policy)

Purpose: externalized policy evaluation with Go performance, matching Java rules.

Policy engine:

- embedded OPA/Rego with prepared queries
- policy file: `services/techgroup-enterprise-travel-policy-go/policy.rego`

Decision log reporting:

- env: `GO_POLICY_DECISION_LOG_ENDPOINT`
- when unset, decision logs fallback to stdout
- signing key: `GO_POLICY_DECISION_LOG_SIGNING_KEY` (HMAC-SHA256)
- masked fields: `tenantId`, `userId`, `conversationId`, `idempotencyKey`

Endpoints:

- `POST /v1/policy/evaluate`
  - request: mirrors TravelRecommendRequest fields
  - response: `{ decision, reason }`

Shadow diff:

- enable `TRAVEL_POLICY_SHADOW=true` to log Java vs Go decisions.

## 3) Registry Cache (go-registry-cache)

Purpose: read-through cache for registry tool list.

Cache engine:

- groupcache with peer list from env (`GROUPCACHE_PEERS`)
- headless-service DNS compatible deployment
- dynamic peer refresh via K8s Endpoints polling
- metrics endpoint: `GET /metrics`
  - `groupcache_peers_count`
  - `groupcache_peer_refresh_timestamp`
  - `groupcache_peer_refresh_errors_total`

Endpoints:

- `GET /v1/cache/get/{key}`
- `POST /v1/cache/set`

Enable:

```bash
export TRAVEL_REGISTRY_CACHE_BACKEND=go
export TRAVEL_REGISTRY_CACHE_URL=http://localhost:8093
```

## 4) Kubernetes overlays

```bash
kubectl apply -k platform/deploy/k8s/kustomize/overlays/dev
kubectl apply -k platform/deploy/k8s/kustomize/overlays/staging
kubectl apply -k platform/deploy/k8s/kustomize/overlays/prod
```

Includes new services:

- services/techgroup-enterprise-travel-ranker-go
- services/techgroup-enterprise-travel-policy-go
- services/techgroup-enterprise-travel-fanout-go
- services/techgroup-enterprise-travel-registry-cache-go (StatefulSet + headless service)

## 5) Canary Gate Automation

Scripts:

- `platform/deploy/scripts/canary_gate.py`
- `platform/deploy/scripts/canary_promote_or_rollback.sh`

Usage:

```bash
python3 platform/deploy/scripts/canary_gate.py --report stress/etcd_migration_compare.json
bash platform/deploy/scripts/canary_promote_or_rollback.sh stress/etcd_migration_compare.json
```

Return code:

- `0`: promote
- `2`: rollback
