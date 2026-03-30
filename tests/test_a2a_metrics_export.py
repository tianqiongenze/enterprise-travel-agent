"""Module provides service components and helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "platform"))
from deploy.scripts import export_a2a_stream_metrics


class _FakeRedisClient:
    def keys(self, pattern: str):
        _ = pattern
        return ["a2a:stream:trip-planner-agent:20260329"]

    def xpending(self, key: str, group: str):
        _ = (key, group)
        return {"pending": 3, "min": "1000-0", "max": "4000-0"}


class _FakeRedisModule:
    class Redis:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = (url, decode_responses)
            return _FakeRedisClient()


class A2AMetricsExportTestCase(unittest.TestCase):
    def test_collect_and_write_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_path = Path(temp_dir) / "a2a.prom"
            with patch.dict("sys.modules", {"redis": _FakeRedisModule}):
                with patch.dict("os.environ", {
                    "TRAVEL_A2A_METRICS_PATH": str(out_path),
                    "TRAVEL_A2A_METRICS_DAY": "20260329",
                    "TRAVEL_A2A_REDIS_URL": "redis://127.0.0.1:7000",
                    "TRAVEL_A2A_KEY_PREFIX": "a2a:stream",
                    "TRAVEL_A2A_STREAM_GROUP": "a2a-consumers",
                }, clear=False):
                    result = export_a2a_stream_metrics.collect_and_write_metrics()
            self.assertEqual(result, out_path)
            text = out_path.read_text(encoding="utf-8")
            self.assertIn("travel_a2a_stream_pending_total 3", text)


if __name__ == "__main__":
    unittest.main()
