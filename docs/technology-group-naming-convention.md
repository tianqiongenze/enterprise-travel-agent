# Technology Group Naming Convention (Enterprise Standard)

## 1. Purpose

This standard enforces consistent naming across Java, Python, Go, frontend, Kubernetes, observability, and documentation artifacts.
All new modules must present clear technology-group ownership and avoid demo-style naming.

## 2. Canonical Prefixes

- Organization prefix: `techgroup`
- Product domain: `enterprise-travel`
- Service pattern: `techgroup-<domain>-<service>`

Examples:

- `techgroup-enterprise-travel-gateway`
- `techgroup-enterprise-travel-runtime`
- `techgroup-enterprise-travel-policy`

## 3. Language-Specific Rules

### Java (Maven + package)

- Maven groupId: `com.techgroup.travel`
- ArtifactId: `techgroup-enterprise-travel-<service>`
- Java package target pattern: `com.techgroup.travel.<service>...`

### Python

- Project name (`pyproject.toml`): `techgroup-enterprise-travel-agent`
- Package namespace target pattern: `techgroup_travel_agent` (migration plan based)
- Distribution tags should keep `techgroup` prefix.

### Go

- Module path: `github.com/techgroup/enterprise-travel-agent/<service>`
- Binary name: `techgroup-<service>`

### Frontend

- NPM package name: `techgroup-enterprise-travel-agent-web`
- Build output artifact: `techgroup-enterprise-travel-web-<version>.tar.gz`

## 4. Platform and Infra Rules

### Kubernetes

- Namespace: `techgroup-travel-<env>`
- Deployment: `techgroup-<service>`
- ConfigMap/Secret: `techgroup-<service>-<purpose>`

### Metrics and Logging

- Metric prefix: `techgroup_travel_`
- Log service field: `service=techgroup-<service>`
- Trace service name: `techgroup-<service>`

## 5. Migration Principles

- Backward compatibility first for externally consumed APIs.
- Keep alias layer for at least one release window when renaming APIs or modules.
- Perform namespace migrations in phases: metadata -> import paths -> runtime env -> deployment manifests.
- Every rename must include test updates and runbook updates.

## 6. Enforcement

- CI should fail on new modules that do not match naming regex.
- Code review checklist must include naming compliance verification.
- Architecture review required for exceptions.

