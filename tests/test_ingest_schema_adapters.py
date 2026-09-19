"""Tests for external benchmark schema adapters and ingest scripts."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from stress.ingest_schema_adapters import parse_benchmark


class IngestSchemaAdaptersTestCase(unittest.TestCase):
    def test_parse_k6_summary(self) -> None:
        sample = {
            "root_group": {},
            "metrics": {
                "vus_max": {"value": 300},
                "http_req_duration": {"values": {"p(95)": 320.5, "p(99)": 700.1}},
                "checks": {"values": {"passes": 990.0, "fails": 10.0}},
            },
        }
        achieved, p95, p99, error, schema = parse_benchmark(sample, "auto")
        self.assertEqual(schema, "k6")
        self.assertEqual(achieved, 300)
        self.assertAlmostEqual(p95, 320.5)
        self.assertAlmostEqual(p99, 700.1)
        self.assertAlmostEqual(error, 1.0)

    def test_parse_jmeter_total(self) -> None:
        sample = {
            "Total": {
                "threads": 120,
                "pct95": 480,
                "pct99": 760,
                "errorPct": 0.5,
            }
        }
        achieved, p95, p99, error, schema = parse_benchmark(sample, "auto")
        self.assertEqual(schema, "jmeter")
        self.assertEqual(achieved, 120)
        self.assertEqual(p95, 480.0)
        self.assertEqual(p99, 760.0)
        self.assertEqual(error, 0.5)

    def test_parse_locust_stats_total(self) -> None:
        sample = {
            "user_count": 80,
            "stats_total": {
                "response_time_percentile_0.95": 120,
                "response_time_percentile_0.99": 200,
                "num_requests": 1000,
                "num_failures": 4,
            },
        }
        achieved, p95, p99, error, schema = parse_benchmark(sample, "auto")
        self.assertEqual(schema, "locust")
        self.assertEqual(achieved, 80)
        self.assertEqual(p95, 120.0)
        self.assertEqual(p99, 200.0)
        self.assertAlmostEqual(error, 0.3984, places=3)

    def test_fault_ingest_can_link_benchmark(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            drill = {
                "scenarios": [
                    {"name": "zone-a", "status": "PASS"},
                    {"name": "zone-b", "status": "PASS"},
                    {"name": "zone-c", "status": "PASS"},
                ],
                "scenarioCount": 3,
                "recoveryRtoMinutes": 10,
                "recoveryRpoSeconds": 30,
                "eventConsumerLagSeconds": 3,
                "eventConsumerDlqTotal": 0,
            }
            benchmark = {
                "root_group": {},
                "metrics": {
                    "vus_max": {"value": 200},
                    "http_req_duration": {"values": {"p(95)": 100, "p(99)": 200}},
                    "checks": {"values": {"passes": 999, "fails": 1}},
                },
            }
            (temp_root / "drill.json").write_text(json.dumps(drill), encoding="utf-8")
            (temp_root / "k6.json").write_text(json.dumps(benchmark), encoding="utf-8")

            out_json = temp_root / "fault_report.json"
            cmd = [
                "python",
                str(repo_root / "stress" / "fault_drill_evidence_ingest.py"),
                "--project-root",
                str(temp_root),
                "--input-json",
                "drill.json",
                "--benchmark-input-json",
                "k6.json",
                "--benchmark-schema",
                "k6",
                "--benchmark-target-concurrency",
                "150",
                "--require-benchmark-pass",
                "--run-id",
                "unit-test-run",
                "--out-json",
                str(out_json),
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertTrue(payload["pass"])
            self.assertIn("linkedBenchmark", payload)
            self.assertTrue(payload["linkedBenchmark"]["pass"])


if __name__ == "__main__":
    unittest.main()

