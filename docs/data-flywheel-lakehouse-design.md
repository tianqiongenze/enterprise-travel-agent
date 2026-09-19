# Data Flywheel + Lakehouse Design (Iceberg/Flink)

## 1. When to Introduce Iceberg and Flink

Recommended for these enterprise scenarios:

- Global multi-region traffic with high event cardinality and long retention.
- Near-real-time recommendation feature updates (minutes/seconds SLA).
- Cross-domain analytics: behavior, recommendation quality, conversion, and operational risk.
- Compliance/audit requirements that need immutable table snapshots and schema evolution.

Not mandatory for small local demo traffic.

## 2. Target Architecture

- Event ingress: Pulsar topics (`recommend.requested`, `recommend.completed`, A2A audit)
- Streaming compute: Flink SQL/DataStream jobs
- Lakehouse storage: Iceberg tables (Bronze/Silver/Gold)
- Online features: city popularity, completion ratios, preference embeddings
- Training loop: periodic model refresh and policy tuning

## 3. Bronze/Silver/Gold Contract

- Bronze: raw event append-only records
- Silver: cleaned and normalized events (schema-validated)
- Gold: domain aggregates and feature snapshots (city/topic/user segments)

## 4. Current Implementation in Repo

- Local flywheel scaffold script: `stress/data_flywheel_pipeline.py`
- Final gate integration: `platform/deploy/scripts/go_live_final_check.py`
- Artifacts:
  - `var/lakehouse/bronze/travel_events.jsonl`
  - `var/lakehouse/silver/travel_events_clean.jsonl`
  - `var/lakehouse/gold/city_features.jsonl`
  - `var/lakehouse/gold/top_topics.jsonl`
  - `var/lakehouse/flywheel_manifest.json`

This gives an executable baseline before migrating to managed Flink + Iceberg.

## 5. Production Upgrade Path

1. Replace local JSONL writer with Flink sink to Iceberg catalog.
2. Add schema registry and event versioning contract checks.
3. Add feature freshness SLO (for example, p95 feature lag <= 5 minutes).
4. Add training/serving skew checks and rollback guardrails.
5. Add immutable evidence snapshot to release artifacts.

