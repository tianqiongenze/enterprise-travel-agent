"""Optional OpenTelemetry tracing for the runtime (lazy, zero hard dependency).

Enable with TRAVEL_OTEL_ENABLED=true and the optional dependencies installed
(``pip install -r requirements-otel-optional.txt``). The service exports OTLP
gRPC to TRAVEL_OTEL_ENDPOINT (default localhost:4317) and injects a W3C
traceparent for inbound X-Trace-Id propagation consistency.
"""

from __future__ import annotations

import logging
import os

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
