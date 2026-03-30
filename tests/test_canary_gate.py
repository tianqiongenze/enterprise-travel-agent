"""Module provides service components and helpers."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


def _load_canary_module():
    script = Path(__file__).resolve().parents[1] / "platform" / "deploy" / "scripts" / "canary_gate.py"
    spec = importlib.util.spec_from_file_location("canary_gate_module", script)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CanaryGateTestCase(unittest.TestCase):
    def test_event_metrics_reasoning(self) -> None:
        mod = _load_canary_module()
        reasons = mod.evaluate_event_consumer(
            {
                "travel_event_consumer_lag_seconds": 120.0,
                "travel_event_consumer_dlq_total": 3.0,
                "travel_event_consumer_processed_total": 0.0,
                "travel_event_consumer_handler_failures_total": 1.0,
            },
            max_lag_seconds=60.0,
            max_dlq_increase=0.0,
        )
        self.assertIn("event_consumer_lag_exceeds_threshold", reasons)
        self.assertIn("event_consumer_dlq_exceeds_threshold", reasons)
        self.assertIn("event_consumer_no_processed_events", reasons)

    def test_load_prometheus_metrics(self) -> None:
        mod = _load_canary_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            p = Path(temp_dir) / "metrics.prom"
            p.write_text(
                "# comment\n"
                "travel_event_consumer_lag_seconds 8\n"
                "travel_event_consumer_processed_total 12\n",
                encoding="utf-8",
            )
            metrics = mod.load_prometheus_metrics(p)
            self.assertEqual(metrics["travel_event_consumer_lag_seconds"], 8.0)
            self.assertEqual(metrics["travel_event_consumer_processed_total"], 12.0)


if __name__ == "__main__":
    unittest.main()
