# P3 Resilience Blueprint

## Scope

P3 adds production hardening for the event pipeline:

1. Retry with bounded backoff
2. Dead-letter queue (DLQ) routing
3. Consumer metrics for Prometheus/Grafana
4. Operational run commands and alert gates
5. Canary gate integration with event-consumer health
6. Java gateway hot-path optimization

## Implementation

### Event consumer

- File: `src/travel_agent/events/consumer.py`
- Features:
  - `RetryPolicy` (`max_retries`, `backoff_ms`, `enable_dlq`)
  - `ConsumerMetrics` (received/processed/retried/dlq/failures/lag)
  - local DLQ file output: `var/events/local_dlq_events.jsonl`
  - pulsar DLQ topic support via producer

### Canary gate integration (P3.5)

- File: `platform/deploy/scripts/canary_gate.py`
- New checks:
  - event metrics file exists (`stress/pulsar_consumer_metrics.prom`)
  - `travel_event_consumer_lag_seconds`
  - `travel_event_consumer_dlq_total`
  - `travel_event_consumer_processed_total`
  - `travel_event_consumer_handler_failures_total`
- New gate args:
  - `--event-metrics`
  - `--max-event-lag-seconds`
  - `--max-event-dlq-total`

### Java optimization (P3.5)

- File: `techgroup-enterprise-travel-gateway/src/main/java/edu/enterprise/travel/gateway/service/PolicyGuardService.java`
- Improvements:
  - short TTL cache for repeated policy checks in canary/go mode
  - request key based on tenant/user/idempotency and control params
  - reduced duplicate remote policy calls under burst traffic

### Runner

- File: `scripts/run_event_consumers.py`
- Usage:

```bash
python scripts/run_event_consumers.py --max-messages 200 --max-retries 3 --retry-backoff-ms 200
```

- Metrics file default:
  - `stress/pulsar_consumer_metrics.prom`

### Alerts & dashboards

- Alert rules: `platform/deploy/monitoring/prometheus-rule.yaml`
  - `EventConsumerLagHigh`
  - `EventConsumerDLQIncreasing`
  - `EventConsumerNoProgress`
  - `EventConsumerHandlerFailuresIncreasing`
- Dashboard:
  - `platform/deploy/monitoring/grafana-dashboard-event-consumer.json`

## Validation

```bash
python -m unittest tests.test_event_bus tests.test_event_consumers tests.test_vector_backends tests.test_capacity_cost_model -v
```

## Go-live gate (P3)

- DLQ growth should remain zero in steady canary windows.
- `travel_event_consumer_lag_seconds` should stay within regional SLO.
- Handler failure increase must trigger incident review before promotion.

## Go-live gate (P3.5)

- Canary must fail promotion when event metrics are missing or lag/DLQ exceed thresholds.
- Java gateway policy cache hit ratio should be monitored in canary windows.

## Go-live gate (P3.6 Final)

- Auto-safemode must execute on rollback with event-related reasons:
  - `platform/deploy/scripts/p3_5_autosafemode.py`
  - output: `deploy/runtime-overrides.env`
  - incident ticket: `stress/p3_5_incident_ticket.json`
- Java policy cache stats endpoint should be available:
  - `GET /api/v1/travel/policy/cache/stats`
- Final promotion requires all of the following:
  - no consumer lag/DLQ/failure alerts in canary window
  - canary gate action = promote
  - rollback drill evidence attached

