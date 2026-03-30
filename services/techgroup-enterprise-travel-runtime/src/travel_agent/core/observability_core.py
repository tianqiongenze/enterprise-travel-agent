"""Module provides service components and helpers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricNames:
    """Metric key contract consumed by alerts and dashboards across stacks."""

    event_processed_total: str = "travel_event_consumer_processed_total"
    event_dlq_total: str = "travel_event_consumer_dlq_total"
    event_queue_full_drop_total: str = "travel_event_consumer_queue_full_drop_total"
    a2a_pending_total: str = "travel_a2a_stream_pending_total"
    a2a_lag_ms: str = "travel_a2a_stream_lag_ms"


@dataclass(frozen=True)
class TraceTags:
    """Trace attribute names kept stable for distributed query parity."""

    tenant_id: str = "tenant.id"
    user_id: str = "user.id"
    policy_id: str = "policy.id"
    engine: str = "orchestration.engine"


@dataclass(frozen=True)
class SLOGates:
    """Default reliability targets used by canary and go-live gates."""

    api_p95_ms: int = 300
    api_p99_ms: int = 700
    error_rate_percent: float = 0.5
    a2a_lag_ms: int = 30000
    event_consumer_lag_seconds: int = 60

