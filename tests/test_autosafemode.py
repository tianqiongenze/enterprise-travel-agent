"""Module provides service components and helpers."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load_module():
    script = Path(__file__).resolve().parents[1] / "platform" / "deploy" / "scripts" / "p3_5_autosafemode.py"
    spec = importlib.util.spec_from_file_location("p3_5_autosafemode", script)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AutoSafemodeTestCase(unittest.TestCase):
    def test_requires_safemode_for_event_reason(self) -> None:
        mod = _load_module()
        self.assertTrue(mod.requires_safemode("rollback", ["event_consumer_lag_exceeds_threshold"]))
        self.assertFalse(mod.requires_safemode("promote", ["event_consumer_lag_exceeds_threshold"]))

    def test_write_override_and_incident(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            override = Path(temp_dir) / "runtime-overrides.env"
            incident = Path(temp_dir) / "incident.json"
            mod.write_runtime_override(override)
            mod.write_incident(incident, "rollback", ["event_consumer_dlq_exceeds_threshold"], override)
            self.assertTrue(override.exists())
            self.assertTrue(incident.exists())
            payload = json.loads(incident.read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "rollback")


if __name__ == "__main__":
    unittest.main()
