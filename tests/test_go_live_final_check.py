"""Module provides service components and helpers."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


def _load_module():
    script = Path(__file__).resolve().parents[1] / "platform" / "deploy" / "scripts" / "go_live_final_check.py"
    spec = importlib.util.spec_from_file_location("go_live_final_check", script)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GoLiveFinalCheckTestCase(unittest.TestCase):
    def test_parse_prom_metrics(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            p = Path(temp_dir) / "m.prom"
            p.write_text("# test\nfoo 1\nbar 2.5\n", encoding="utf-8")
            data = mod._parse_prom_metrics(p)
            self.assertEqual(data["foo"], 1.0)
            self.assertEqual(data["bar"], 2.5)

    def test_run_all_checks_generates_summary(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "stress").mkdir(parents=True, exist_ok=True)
            (root / "deploy" / "scripts").mkdir(parents=True, exist_ok=True)
            (root / "stress" / "etcd_migration_compare.json").write_text('{"summary": {}}', encoding="utf-8")
            (root / "stress" / "canary_gate_decision.json").write_text('{"action": "promote", "reasons": []}', encoding="utf-8")
            (root / "stress" / "canary_gate_metrics.prom").write_text('canary_gate_event_consumer_lag_seconds 0\ncanary_gate_event_consumer_dlq_total 0\n', encoding="utf-8")
            (root / "stress" / "capacity_cost_report.json").write_text('{}', encoding="utf-8")
            (root / "stress" / "capacity_cost_report.md").write_text('# x', encoding="utf-8")

            args = SimpleNamespace(
                python_exec="python",
                run_tests=False,
                run_java_compile=False,
                run_canary_gate=False,
                run_capacity_model=False,
                max_event_lag=60.0,
                max_event_dlq=0.0,
                peak_connected=1_000_000,
                active_ratio=0.1,
            )
            report = mod.run_all_checks(root, args)
            self.assertIn("summary", report)
            self.assertIn("checks", report)
            self.assertTrue(len(report["checks"]) > 0)


if __name__ == "__main__":
    unittest.main()
