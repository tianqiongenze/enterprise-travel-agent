# Core Modules Alignment (Python/Java/Go)

## Common Modules

### policy-core

- Purpose: unify tier/tool/engine policy semantics
- Canonical file: `policy-core/policy-core.v1.json`
- Golden cases: `policy-core/cases/golden_cases.v1.json`

### guard-core

- Purpose: unify rate-limit/idempotency/circuit contracts
- Python skeleton: `src/travel_agent/core/guard_core.py`
- Runtime implementation: `src/travel_agent/traffic_guard.py`

### messaging-core

- Purpose: unify A2A + Pulsar delivery semantics and retry policy
- Python skeleton: `src/travel_agent/core/messaging_core.py`
- Runtime implementation: `src/travel_agent/a2a/router.py`, `src/travel_agent/events/consumer.py`

### observability-core

- Purpose: unify metric names, trace tags, and SLO gates
- Python skeleton: `src/travel_agent/core/observability_core.py`
- Runtime usage: prometheus rules and dashboards under `platform/deploy/monitoring/`

## Scale-Oriented Conventions

- at-least-once delivery with idempotency keys
- bounded queue + worker pool for consumer backpressure
- cache-first policy validation with short TTL fallback
- explicit metric naming and alerting contracts

## Recommended Next Step

- Generate language stubs from policy-core schema for stricter parity checks.

