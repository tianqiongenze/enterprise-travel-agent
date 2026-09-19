# TechGroup Repository Structure Enterprise Standard

## 1. Goal

This standard defines a regulated repository layout for enterprise-scale delivery.
It avoids ad-hoc directory growth and keeps engineering, security, and compliance workflows consistent.

## 2. Target Top-Level Layout

```text
enterprise-travel-agent/
  apps/                      # user-facing applications (web, miniapp)
  services/                  # backend services (gateway/runtime/policy/ranker/fanout/cache)
  platform/                  # deployment, observability, infra automation
  data-contracts/            # schemas, policy-core, API contracts
  docs/                      # architecture/runbooks/specs
  scripts/                   # developer and CI helper scripts
  tests/                     # cross-module test suites
  assets/                    # immutable static assets
```

## 3. Current-to-Target Mapping (Migration Baseline)

| Current directory | Target directory | Status |
|---|---|---|
| `techgroup-enterprise-travel-gateway/` | `services/techgroup-enterprise-travel-gateway/` | Phase-2 planned |
| `src/` | `services/techgroup-enterprise-travel-runtime/` | Phase-2 planned |
| `go-policy/` | `services/techgroup-enterprise-travel-policy-go/` | Phase-3 completed |
| `go-ranker/` | `services/techgroup-enterprise-travel-ranker-go/` | Phase-3 completed |
| `go-fanout/` | `services/techgroup-enterprise-travel-fanout-go/` | Phase-3 completed |
| `go-registry-cache/` | `services/techgroup-enterprise-travel-registry-cache-go/` | Phase-3 completed |
| `apps/techgroup-enterprise-travel-web/` | `apps/techgroup-enterprise-travel-web/` | Phase-2 planned |
| `miniapp-wechat/` | `apps/techgroup-enterprise-travel-miniapp-wechat/` | Phase-4 planned |
| `deploy/` | `platform/deploy/` | Phase-2 planned |
| `policy-core/` | `data-contracts/policy-core/` | Phase-2 planned |
| `skills/` | `data-contracts/skills/` | Phase-4 planned |
| `data/` | `data-contracts/seed-data/` | Phase-4 planned |

## 4. Naming Rules

- Directory pattern: `techgroup-<domain>-<service>`
- Java Maven groupId: `com.techgroup.travel`
- Go module: `github.com/techgroup/enterprise-travel-agent/<service>`
- Python project metadata: `techgroup-enterprise-travel-agent`
- NPM package names: `techgroup-enterprise-travel-<app>`

## 5. Migration Execution Plan

### Phase-1 (completed in this change)

- Renamed `spring-gateway` -> `techgroup-enterprise-travel-gateway`
- Updated root CI/test commands and docs references
- Upgraded JUnit/Surefire alignment to avoid IDE discovery mismatch

### Phase-2 (high priority)

- Introduce `services/`, `apps/`, `platform/`, `data-contracts/` umbrella directories
- Move runtime and gateway services under `services/`
- Update CI and deployment manifests to new paths

### Phase-3 (medium priority)

- Move all Go services into `services/` with enterprise service names
- Align Dockerfiles, K8s manifests, and release scripts

### Phase-4 (controlled rollout)

- Move miniapp and contract data directories
- Deprecate legacy paths with compatibility symlink/alias strategy

## 6. Governance

- Any new top-level directory requires architecture review approval.
- CI should reject non-compliant new module names.
- Every path migration must include test updates and rollback instructions.

