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

## Distributed evidence pipelines (for PRODUCTION_PROVEN gate)

Generate distributed benchmark evidence:

```bash
python3 stress/distributed_benchmark_evidence.py --target-concurrency 1000000 --achieved-concurrency 1000000 --regions 3 --duration-minutes 60
```

Generate multi-region fault drill evidence:

```bash
python3 stress/multi_region_fault_drill.py --scenario-count 3 --passed-scenarios 3 --recovery-rto-minutes 10 --recovery-rpo-seconds 30
```

Then aggregate readiness:

```bash
python3 stress/global_scale_readiness.py --target-concurrency 1000000
```

## External evidence ingest (recommended for real PRODUCTION_PROVEN)

```bash
export TRAVEL_EVIDENCE_SIGNING_KEY="replace-with-strong-key"
python3 stress/distributed_benchmark_ingest.py --input-json stress/report_5k.json --run-id 2026M04D02-benchmark --environment staging
python3 stress/fault_drill_evidence_ingest.py --input-json stress/multi_region_fault_drill_report.json --run-id 2026M04D02-drill --environment staging
```

Then run hard gate:

```bash
python3 platform/deploy/scripts/go_live_final_check.py --min-scale-status PRODUCTION_PROVEN
```

Schema adapters for common load-test exports:

```bash
# k6 summary json
python3 stress/distributed_benchmark_ingest.py --input-json path/to/k6-summary.json --schema k6 --run-id run-k6-001 --environment staging

# JMeter statistics.json
python3 stress/distributed_benchmark_ingest.py --input-json path/to/jmeter-statistics.json --schema jmeter --run-id run-jmeter-001 --environment staging

# Locust json export
python3 stress/distributed_benchmark_ingest.py --input-json path/to/locust-stats.json --schema locust --run-id run-locust-001 --environment staging
```

Cross-platform one-click deployment/load-test scripts:

```bash
# Linux
bash platform/deploy/scripts/one_click_stack_linux.sh

# macOS
bash platform/deploy/scripts/one_click_stack_macos.sh
```

```powershell
# Windows PowerShell
powershell -ExecutionPolicy Bypass -File platform/deploy/scripts/one_click_stack_windows.ps1
```

