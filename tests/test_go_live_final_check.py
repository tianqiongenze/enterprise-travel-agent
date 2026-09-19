"""Module provides service components and helpers."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


def _load_module():
    script = Path(__file__).resolve().parents[1] / "platform" / "deploy" / "scripts" / "go_live_final_check.py"
    spec = importlib.util.spec_from_file_location("go_live_final_check", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
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

    def test_security_env_gate_local_demo_secret_warns_but_passes(self) -> None:
        import os
        from unittest.mock import patch

        mod = _load_module()
        env = {"TRAVEL_INTERNAL_SHARED_SECRET": "demo-internal-secret", "TRAVEL_AUTH_MODE": "internal"}
        with patch.dict(os.environ, env, clear=False):
            result = mod._security_env_gate("local")
        self.assertEqual(result.status, "PASS")
        self.assertIn("WARNING", result.detail)

    def test_security_env_gate_staging_rejects_demo_secret(self) -> None:
        import os
        from unittest.mock import patch

        mod = _load_module()
        env = {"TRAVEL_INTERNAL_SHARED_SECRET": "demo-internal-secret", "TRAVEL_AUTH_MODE": "internal"}
        with patch.dict(os.environ, env, clear=False):
            result = mod._security_env_gate("staging")
        self.assertEqual(result.status, "FAIL")
        self.assertIn("demo value", result.detail)

    def test_security_env_gate_prod_requires_oidc_and_semantic_embeddings(self) -> None:
        import os
        from unittest.mock import patch

        mod = _load_module()
        env = {
            "TRAVEL_INTERNAL_SHARED_SECRET": "real-secret",
            "TRAVEL_AUTH_MODE": "internal",
            "TRAVEL_SECURITY_MODE": "off",
            "TRAVEL_EMBEDDING_BACKEND": "hash",
        }
        with patch.dict(os.environ, env, clear=False):
            result = mod._security_env_gate("prod")
        self.assertEqual(result.status, "FAIL")
        self.assertIn("oidc", result.detail)
        self.assertIn("oauth2", result.detail)
        self.assertIn("hash", result.detail)

    def test_security_env_gate_prod_passes_with_oidc(self) -> None:
        import os
        from unittest.mock import patch

        mod = _load_module()
        env = {
            "TRAVEL_INTERNAL_SHARED_SECRET": "real-secret",
            "TRAVEL_AUTH_MODE": "oidc",
            "TRAVEL_SECURITY_MODE": "oauth2",
            "TRAVEL_EMBEDDING_BACKEND": "local-model",
        }
        with patch.dict(os.environ, env, clear=False):
            result = mod._security_env_gate("prod")
        self.assertEqual(result.status, "PASS")

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
            (root / "stress" / "global_scale_readiness_report.json").write_text('{"status":"NOT_READY"}', encoding="utf-8")
            (root / "stress" / "global_scale_readiness_report.md").write_text('# readiness', encoding="utf-8")

            args = SimpleNamespace(
                python_exec="python",
                run_tests=False,
                run_java_compile=False,
                run_canary_gate=False,
                run_capacity_model=False,
                run_distributed_benchmark=False,
                run_fault_drill=False,
                run_dr_automation=False,
                dr_auto_run=False,
                dr_incident_out="stress/dr_automation_incident.json",
                dr_status_out="stress/dr_automation_status.json",
                run_data_flywheel=False,
                run_scale_readiness=False,
                max_event_lag=60.0,
                max_event_dlq=0.0,
                peak_connected=1_000_000,
                active_ratio=0.1,
                target_concurrency=1_000_000,
                distributed_regions=3,
                distributed_duration_minutes=60,
                distributed_report_json="stress/report_5k.json",
                distributed_evidence_source="local-loadtest",
                distributed_run_id="local-unknown",
                distributed_environment="local",
                fault_recovery_rto_minutes=10,
                fault_recovery_rpo_seconds=30,
                fault_canary_decision="stress/canary_gate_decision.json",
                fault_canary_metrics="stress/canary_gate_metrics.prom",
                fault_incident_ticket="stress/p3_5_incident_ticket.json",
                fault_evidence_source="staging-drill",
                fault_run_id="drill-unknown",
                fault_environment="staging",
                flywheel_events="var/events/audit_events.jsonl",
                flywheel_out_root="var/lakehouse",
                run_flywheel_sla=False,
                feature_freshness_sec=600.0,
                training_latency_sec=1200.0,
                feedback_lag_sec=180.0,
                run_flink_iceberg_config_check=False,
                iceberg_catalog_type="hive",
                require_faiss=False,
                evidence_signing_key_env="TRAVEL_EVIDENCE_SIGNING_KEY",
                max_evidence_age_hours=24.0,
                allowed_evidence_environments="staging,prod",
                require_evidence_signature=False,
                require_source_protection=False,
                min_scale_status="NOT_READY",
                require_slo_enforcement=False,
                slo_max_success_gap=0.03,
                slo_max_p95_drift=0.08,
                slo_max_p99_drift=0.10,
                slo_max_runtime_error_rate=0.01,
            )
            report = mod.run_all_checks(root, args)
            self.assertIn("summary", report)
            self.assertIn("checks", report)
            self.assertTrue(len(report["checks"]) > 0)


if __name__ == "__main__":
    unittest.main()
