# Ops Production Handoff

## Release Script Bundle

Location: `deploy/scripts/`

- `preflight.sh` — dependency and required-file checks
- `build_release.sh` — backend tests + gateway tests + web production build
- `deploy_release.sh` — `docker compose up -d`
- `healthcheck_release.sh` — runtime/gateway/web health checks
- `rollback_release.sh` — fast rollback by stopping deployed services
- `canary_gate.py` — evaluate canary report and output promote/rollback
- `canary_promote_or_rollback.sh` — executable gate wrapper for release pipeline

## Monitoring Assets

Location: `deploy/monitoring/`

- `prometheus-rule.yaml` — PrometheusRule alerts for groupcache peer health and canary gate thresholds
- `grafana-dashboard-go-runtime.json` — Grafana dashboard for groupcache runtime and canary gate status/drift

K8s integration:

- `deploy/k8s/kustomize/base/kustomization.yaml` includes `../../monitoring/prometheus-rule.yaml`

## Recommended Execution Order

```bash
./deploy/scripts/preflight.sh
./deploy/scripts/build_release.sh
./deploy/scripts/deploy_release.sh
./deploy/scripts/healthcheck_release.sh
```

Rollback command:

```bash
./deploy/scripts/rollback_release.sh
```

Canary gate:

```bash
./deploy/scripts/canary_promote_or_rollback.sh stress/etcd_migration_compare.json
```

Canary metrics export options:

- local text metrics file (default): `stress/canary_gate_metrics.prom`
- optional Pushgateway publish:

```bash
export CANARY_GATE_PUSHGATEWAY_URL=http://pushgateway.monitoring.svc:9091
export CANARY_GATE_PUSHGATEWAY_JOB=canary_gate
./deploy/scripts/canary_promote_or_rollback.sh stress/etcd_migration_compare.json
```

CI Gate Behavior:

- when `stress/etcd_migration_compare.json` exists in pipeline workspace,
  `canary_promote_or_rollback.sh` is enforced and non-zero blocks release.
- when report is absent, pipeline logs "skip gate" and continues.

## Required Environment Variables

- `TRAVEL_RUNTIME_BASE_URL` for spring gateway
- `VITE_TRAVEL_API_BASE_URL` for web frontend
- `TRAVEL_INTERNAL_SHARED_SECRET` for runtime/gateway signing
- `GO_POLICY_DECISION_LOG_SIGNING_KEY` for policy decision log HMAC signing

## Security and Ingress

- Production nginx template: `deploy/nginx/nginx.conf`
- Includes HTTPS redirect, TLS, HSTS, CSP, and API/runtime rate limits

## Final Gates

- Checklist: `docs/go-live-checklist.md`
- Runbook: `docs/release-runbook.md`
- Manual 100万记录测试：`docs/manual-1m-record-testing.md`
