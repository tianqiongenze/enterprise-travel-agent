"""Module provides service components and helpers."""

import unittest

from stress.etcd_migration_drill import compare_reports, render_markdown_report


class MigrationDrillTestCase(unittest.TestCase):
    def test_compare_reports_detects_consistent_results(self) -> None:
        legacy = {
            "mode": "legacy",
            "success_rate": 1.0,
            "avg_latency_ms": 120.0,
            "p95_latency_ms": 180.0,
            "p99_latency_ms": 210.0,
            "missing_service_errors": 5,
            "missing_tool_errors": 5,
            "sample_size": 20,
        }
        new = {
            "mode": "new",
            "success_rate": 1.0,
            "avg_latency_ms": 130.0,
            "p95_latency_ms": 190.0,
            "p99_latency_ms": 220.0,
            "missing_service_errors": 5,
            "missing_tool_errors": 5,
            "sample_size": 20,
        }
        summary = compare_reports(legacy, new)
        self.assertEqual(summary["consistency_status"], "pass")

    def test_compare_reports_detects_inconsistent_results(self) -> None:
        legacy = {
            "mode": "legacy",
            "success_rate": 1.0,
            "avg_latency_ms": 120.0,
            "p95_latency_ms": 180.0,
            "p99_latency_ms": 210.0,
            "missing_service_errors": 5,
            "missing_tool_errors": 5,
            "sample_size": 20,
        }
        new = {
            "mode": "new",
            "success_rate": 0.8,
            "avg_latency_ms": 240.0,
            "p95_latency_ms": 400.0,
            "p99_latency_ms": 600.0,
            "missing_service_errors": 2,
            "missing_tool_errors": 1,
            "sample_size": 20,
        }
        summary = compare_reports(legacy, new)
        self.assertEqual(summary["consistency_status"], "fail")
        self.assertTrue(len(summary["fail_reasons"]) >= 1)

    def test_render_markdown_report_contains_sections(self) -> None:
        legacy = {"mode": "legacy", "success_rate": 1.0, "avg_latency_ms": 100, "p95_latency_ms": 150, "p99_latency_ms": 180, "missing_service_errors": 4, "missing_tool_errors": 4, "sample_size": 10}
        new = {"mode": "new", "success_rate": 1.0, "avg_latency_ms": 110, "p95_latency_ms": 160, "p99_latency_ms": 190, "missing_service_errors": 4, "missing_tool_errors": 4, "sample_size": 10}
        summary = compare_reports(legacy, new)
        markdown = render_markdown_report(legacy, new, summary)
        self.assertIn("## 1. Comparison Summary", markdown)
        self.assertIn("## 2. Metric Table", markdown)
        self.assertIn("## 3. Gate Decision", markdown)


if __name__ == "__main__":
    unittest.main()
