"""Trace wiring tests (item 5: OTel three-tier wiring).

Two layers:
- configure/propagation layer runs everywhere (otel mocked when absent locally).
- real span emission path runs when opentelemetry is installed (CI installs
  requirements-otel-optional.txt); skipped locally when it is not.
"""

import os
import unittest
from unittest import mock


def _otel_available() -> bool:
    try:
        import opentelemetry.sdk  # noqa: F401

        return True
    except ImportError:
        return False


class TraceWiringTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("TRAVEL_OTEL_ENABLED", "TRAVEL_OTEL_ENDPOINT", "TRAVEL_OTEL_SERVICE_NAME")}
        os.environ["TRAVEL_OTEL_ENABLED"] = "true"

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_disabled_by_default(self):
        os.environ["TRAVEL_OTEL_ENABLED"] = "false"
        from src.travel_agent.observability import tracing

        with mock.patch.object(tracing, "_configured", False):
            self.assertFalse(tracing.configure_tracing())
            with tracing.trace_recommendation("t-1", "tenant-a", "langgraph") as span:
                span.set_attribute("k", "v")

    def test_configure_skips_gracefully_without_otel(self):
        from src.travel_agent.observability import tracing

        if _otel_available():
            self.skipTest("opentelemetry installed; graceful-degradation path not applicable")
        with mock.patch.object(tracing, "_configured", False):
            self.assertFalse(tracing.configure_tracing())

    def test_trace_recommendation_null_span_never_raises(self):
        from src.travel_agent.observability import tracing

        with mock.patch.object(tracing, "_configured", False):
            with tracing.trace_recommendation("web-x", "tenant-a", "agentscope") as span:
                span.set_attribute("travel.trace_id", "web-x")
                span.record_exception(ValueError("boom"))
            with tracing.start_span("travel_agent.unit") as span:
                span.end()

    def test_app_module_calls_configure_tracing(self):
        import importlib

        import src.travel_agent.api.app as app_module

        with mock.patch("src.travel_agent.observability.tracing.configure_tracing", return_value=False) as configure:
            importlib.reload(app_module)
        self.assertTrue(configure.called)


@unittest.skipUnless(_otel_available(), "opentelemetry not installed (pip install -r requirements-otel-optional.txt)")
class RealSpanEmissionTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("TRAVEL_OTEL_ENABLED",)}
        os.environ["TRAVEL_OTEL_ENABLED"] = "true"

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_spans_emitted_and_x_trace_id_bridged(self):
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        from src.travel_agent.observability import tracing

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        otel_trace.set_tracer_provider(provider)

        with mock.patch.object(tracing, "_configured", True):
            with tracing.trace_recommendation("web-123-abc", "tenant-a", "agentscope") as span:
                span.set_attribute("travel.engine", "agentscope")

        spans = exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        attrs = dict(spans[0].attributes or {})
        self.assertEqual(attrs.get("travel.trace_id"), "web-123-abc")
        self.assertEqual(attrs.get("travel.tenant_id"), "tenant-a")
        self.assertEqual(spans[0].name, "travel_agent.recommend")


if __name__ == "__main__":
    unittest.main()
