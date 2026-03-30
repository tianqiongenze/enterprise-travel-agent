# Stress Testing Guide

## Quick run

```bash
python3 stress/load_test.py --base-url http://localhost:8000 --requests 2000 --concurrency 200 --out stress/report.json
```

## Etcd migration drill (legacy vs new)

```bash
python3 stress/etcd_migration_drill.py \
  --legacy-base-url http://localhost:8000 \
  --new-base-url http://localhost:8001 \
  --requests 200 \
  --concurrency 20 \
  --out-json stress/etcd_migration_compare.json \
  --out-md stress/etcd_canary_report.md
```

This generates:

- JSON comparison evidence
- Markdown canary gate report for classroom/public sharing

## What this validates

- API correctness under concurrent request bursts
- latency metrics (avg/p95/p99)
- error rates and status distribution

## Important note

This local harness validates single-node behavior only. It does **not** prove 1M concurrent or 100M user capacity by itself.
