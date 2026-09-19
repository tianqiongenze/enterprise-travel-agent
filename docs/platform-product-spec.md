# Enterprise Travel Agent Platform Product Specification

## 1. Product Positioning

Enterprise Travel Agent is a policy-governed multi-agent recommendation platform for travel planning.
It combines gateway policy control, runtime orchestration, and optional Go acceleration services.

## 2. Target Users

- B2B travel operations teams
- enterprise employee travel portals
- platform SRE and policy governance teams

## 3. Core Capabilities

- Multi-agent orchestration (`Manager`, `RouteMaking`, `TripPlanner`, extension agents)
- Unified policy guard (tools, steps, calls, membership tier)
- Gateway + runtime separation for enterprise integration
- Event/audit pipeline with optional Pulsar mirror
- Cache, idempotency, rate limit, circuit breaker safety rails
- Optional Go services for ranker/policy/fanout/registry-cache

## 4. Functional Scope

### 4.1 Recommendation Flow

1. Client submits recommendation request to Spring Gateway.
2. Gateway performs policy validation and request shaping.
3. Gateway calls Python runtime `/runtime/recommend`.
4. Runtime runs orchestration and tool calls.
5. Gateway merges runtime payload and AI rationale.
6. Gateway returns unified response and mirrors audit events.

### 4.2 Guard and Compliance

- tool whitelist enforced per membership tier
- `maxAgentSteps` and `maxToolCalls` hard guard
- idempotency key deduplication
- per-user/per-scope rate limiting
- downstream circuit breaker control

### 4.3 Observability

- policy cache stats API
- consumer metrics export (`.prom`)
- dashboard and alert rules under `platform/deploy/monitoring/`
- trace propagation via `X-Trace-Id` and `traceparent`

## 5. Non-Functional Requirements

- Availability target: 99.9% for gateway API in production clusters
- Performance baseline (default SLO gates):
  - `p95 <= 300ms`
  - `p99 <= 700ms`
- Safe degradation when optional dependencies fail:
  - Pulsar unavailable -> local/event fallback
  - AI key unavailable -> rationale fallback text
  - Go optional services unavailable -> Python fallback path

## 6. API Contract (external)

- `GET /api/v1/travel/health`
- `GET /api/v1/travel/policy/cache/stats`
- `POST /api/v1/travel/recommend`

Mandatory request fields:

- tenant context: `tenantId`, `userId`, `policyId`, `conversationId`, `idempotencyKey`
- travel intent: `city`, `days`, `budget`, `travelers`, `preferences`
- guard controls: `maxAgentSteps`, `maxToolCalls`, `allowedTools`

## 7. Deployment Scope

- Local integration via `platform/deploy/docker-compose.yml`
- K8s manifests under `platform/deploy/k8s/`
- Kustomize overlays (`dev`, `staging`, `prod`)
- Release scripts under `platform/deploy/scripts/`

## 8. Risks and Mitigation

- Policy drift between Java/Python/Go -> maintain `policy-core` golden cases and parity tests
- Event backlog growth -> bounded queue + worker pool + DLQ handling
- Cache inconsistency -> short TTL and fallback to live evaluation
- Canary regressions -> gate scripts and rollback automation

## 9. Acceptance Criteria

- Gateway tests pass (`mvn test` in `techgroup-enterprise-travel-gateway`)
- Core runtime tests pass (`python -m unittest discover -s tests -p "test_*.py" -v`)
- API docs available for developers/users
- Product spec published and linked from project docs

## 10. Industrial Scale Target (Capacity Planning Goal - Not Yet Proven)

> NOTE: 10B registered users / 10M concurrent is a long-term capacity PLANNING goal used for
> architecture sizing. It is NOT a measured or achieved state. Current measured evidence is
> tracked in `stress/` (e.g. achievedConcurrency=300 in the local evidence set) and the
> readiness status is `ARCHITECTURE_READY_NOT_PROVEN`.

### 10.1 Capacity decomposition

- Registered users: `10,000,000,000`
- Peak concurrent sessions: `10,000,000`
- Peak active generation ratio: `8% ~ 15%`
- Peak active AI requests: `800,000 ~ 1,500,000`

Sizing formula:

- `gateway_pods = peak_connected / conn_per_pod * safety_factor`
- `runtime_pods = peak_active / active_slots_per_pod * safety_factor`

With enterprise baseline assumptions:

- gateway `conn_per_pod = 12,000`
- runtime `active_slots_per_pod = 120`
- `safety_factor = 2.0`

Estimated baseline:

- gateway pods: `10,000,000 / 12,000 * 2.0 ~= 1,667`
- runtime pods (`1,000,000` active requests): `1,000,000 / 120 * 2.0 ~= 16,667`

These numbers are planning baselines and must be validated with distributed stress tests.

### 10.2 Data and traffic partitioning

- Tenant + region + user hash as primary sharding keys.
- Gateway stateless scale-out; runtime isolated by tenant class and SLA tier.
- Redis/Pulsar/vector backends partitioned by tenant and region domain.
- Use strict idempotency and replay-safe design for all at-least-once paths.

### 10.3 Reliability objectives

- API availability: `>= 99.95%` for platinum tenants.
- Error budget split by tier and region.
- Multi-region RTO: `<= 5 min`, RPO: `<= 1 min` for critical audit streams.

## 11. Implementation Upgrade Roadmap

### Phase P0 (0-3 months)

- Standardize API error contracts and CI gates.
- Enforce policy-core parity tests across Java/Python/Go.
- Deploy active-active in 3 regions with canary rollout automation.

### Phase P1 (3-6 months)

- Introduce tenant QoS classes (gold/silver/basic) with hard quotas.
- Enable adaptive concurrency, queue backpressure, and circuit governance.
- Build centralized traffic replay platform for deterministic incident recovery.

### Phase P2 (6-12 months)

- Split control plane and data plane clusters by tenant segment.
- Introduce cost-aware scheduler for runtime/model/tool routing.
- Add global traffic engineering with policy-aware failover orchestration.

### Phase P3 (12+ months)

- Continuous chaos engineering in production-like environments.
- Full compliance automation for audit, data residency, and retention policies.
- Capacity auto-planning with predictive scaling from historical demand signals.

## 12. Test and Release Upgrade Requirements

- Unit tests: every commit, blocking merge.
- Contract tests: API + policy-core parity + schema compatibility.
- Distributed load tests: before each major release (peak + sustained + failure storm).
- Resilience drills: region outage, MQ lag storm, cache split-brain, registry partition.
- Release gating: canary + shadow + SLO + rollback automation all green.

## 13. Technology Group Naming Requirement

- Java Maven coordinates use `com.techgroup.travel` prefix.
- Go modules use `github.com/techgroup/enterprise-travel-agent/...`.
- Python package metadata uses `techgroup-enterprise-travel-agent`.
- Frontend package name uses `techgroup-enterprise-travel-agent-web`.
- All new services and docs should follow `techgroup-<domain>-<service>` naming.

