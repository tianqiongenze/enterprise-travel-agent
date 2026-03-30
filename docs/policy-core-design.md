# Policy-Core Unified Specification Design

## Goal

`policy-core` is the single source of truth for:

- membership tier capability matrix
- tool access permissions
- orchestration engine permissions
- policy limits (`maxAgentSteps`, `maxToolCalls`)
- engine alias normalization

Primary artifact:

- `policy-core/policy-core.v1.json`

Golden parity cases:

- `policy-core/cases/golden_cases.v1.json`

## Runtime Mapping

### Python

- `src/travel_agent/access/control.py`
  - loads `policy-core.v1.json`
  - provides `evaluate_policy(...)`
- `src/travel_agent/api/app.py`
  - enforces decision result before recommendation execution

### Java (Gateway)

- `techgroup-enterprise-travel-gateway/src/main/java/edu/enterprise/travel/gateway/service/PolicyCoreSpec.java`
  - loads `policy-core.v1.json`
- `techgroup-enterprise-travel-gateway/src/main/java/edu/enterprise/travel/gateway/service/PolicyGuardService.java`
  - uses `PolicyCoreSpec` for tier/tool/engine decision

### Go (Policy Service)

- `services/techgroup-enterprise-travel-policy-go/policy_core.go`
  - loads `policy-core.v1.json`
  - provides engine alias normalization helper
- `services/techgroup-enterprise-travel-policy-go/main.go`
  - maps request through `policyCoreNormalizeEngine(...)`

## Performance Notes

- policy-core file is loaded once at process startup
- hot-path checks remain in-memory maps/sets
- language-specific short-TTL caches remain enabled

## Design Principles

- single source of truth for policy semantics
- backward-compatible schema evolution
- separation of policy semantics vs transport/runtime details
- deterministic reason strings for cross-language parity

## Evolution Plan

### v1

- tier/tool/engine matrix
- step/call limits
- alias mapping

### v2 (recommended)

- per-tenant overrides
- risk-level tool categories
- dynamic policy distribution via control plane
- signed policy bundles with version pinning

