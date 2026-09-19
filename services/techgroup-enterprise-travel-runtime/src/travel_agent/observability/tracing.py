"""Optional OpenTelemetry tracing for the runtime (lazy, zero hard dependency).

Enable with TRAVEL_OTEL_ENABLED=true and the optional dependencies installed
(``pip install -r requirements-otel-optional.txt``). The service exports OTLP
gRPC to TRAVEL_OTEL_ENDPOINT (default localhost:4317) and injects a W3C
traceparent for inbound X-Trace-Id propagation consistency.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger("travel_agent.otel")

_configured = False


def is_enabled() -> bool:
    return os.getenv("TRAVEL_OTEL_ENABLED", "false").strip().lower() == "true"


def configure_tracing() -> bool:
    """Install OTel tracing when enabled and available. Returns True on success."""
    global _configured
    if _configured:
        return True
    if not is_enabled():
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as error:
        logger.warning(
            "TRAVEL_OTEL_ENABLED=true but opentelemetry packages are missing "
            "(pip install -r requirements-otel-optional.txt): %s",
            error,
        )
        return False

    endpoint = os.getenv("TRAVEL_OTEL_ENDPOINT", "http://localhost:4317")
    resource = Resource.create(
        {
            "service.name": os.getenv("TRAVEL_OTEL_SERVICE_NAME", "travel-agent-runtime"),
            "deployment.environment": os.getenv("TRAVEL_ENV", "local"),
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    _configured = True
    logger.info("otel tracing configured (endpoint=%s)", endpoint)
    return True


def tracer(name: str = "travel_agent.runtime"):
    from opentelemetry import trace

    return trace.get_tracer(name)


def start_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Start a span on the runtime tracer. Returns a no-op CM when otel is off."""
    if not is_enabled() or not _configured:
        return _NullSpan()
    span = tracer().start_span(name, attributes=attributes or {})
    return span


class _NullSpan:
    """Stand-in span used when OpenTelemetry is disabled or unavailable."""

    def __enter__(self) -> "_NullSpan":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def record_exception(self, exception: BaseException) -> None:
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def end(self) -> None:
        pass


@contextmanager
def trace_recommendation(trace_id: str, tenant_id: str, engine: str) -> Iterator[Any]:
    """Span wrapping a full recommendation; bridges the gateway X-Trace-Id."""
    span = start_span(
        "travel_agent.recommend",
        attributes={
            "travel.trace_id": trace_id,
            "travel.tenant_id": tenant_id,
            "travel.engine": engine,
        },
    )
    try:
        yield span
    except Exception as error:
        span.record_exception(error)
        raise
    finally:
        span.end()
