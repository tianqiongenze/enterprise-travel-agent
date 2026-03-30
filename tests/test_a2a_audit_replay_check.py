"""Module provides service components and helpers."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from stress.a2a_audit_replay_check import run


class A2AAuditReplayCheckTestCase(unittest.TestCase):
    def test_report_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "a2a_audit_events.jsonl"
            rows = [
                {"topic": "a2a.route_plan", "payload": {"id": "m1", "sender": "manager"}},
                {"topic": "a2a.route_plan", "payload": {"id": "m1", "sender": "manager"}},
                {"topic": "a2a.trip_plan", "payload": {"id": "m2", "sender": "manager"}},
            ]
            path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in rows), encoding="utf-8")

            report = run(path, max_duplicates=0)
            self.assertTrue(report.get("ok"))
            self.assertEqual(report.get("total"), 3)
            self.assertEqual(report.get("duplicate_ids"), 1)
            self.assertFalse(report.get("gate_pass"))

    def test_window_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "a2a_audit_events.jsonl"
            now = datetime.now(timezone.utc)
            old = now.replace(year=max(2000, now.year - 1))
            rows = [
                {"ts": old.isoformat(), "topic": "a2a.route_plan", "payload": {"id": "m1"}},
                {"ts": now.isoformat(), "topic": "a2a.route_plan", "payload": {"id": "m2"}},
            ]
            path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in rows), encoding="utf-8")

            report = run(path, window_minutes=10)
            self.assertTrue(report.get("ok"))
            self.assertEqual(report.get("filtered_out"), 1)


if __name__ == "__main__":
    unittest.main()

