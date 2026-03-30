"""Module provides service components and helpers."""

import json
import unittest
from pathlib import Path

from src.travel_agent.access.control import evaluate_policy


class PolicyCoreParityTestCase(unittest.TestCase):
    def test_golden_cases(self) -> None:
        cases_path = Path(__file__).resolve().parents[1] / "data-contracts" / "policy-core" / "cases" / "golden_cases.v1.json"
        rows = json.loads(cases_path.read_text(encoding="utf-8"))
        self.assertTrue(isinstance(rows, list) and len(rows) > 0)

        for case in rows:
            name = str(case.get("name", ""))
            payload = case.get("input", {}) if isinstance(case, dict) else {}
            expected = case.get("expected", {}) if isinstance(case, dict) else {}
            decision = evaluate_policy(
                tier=str(payload.get("tier", "basic")),
                engine=str(payload.get("engine", "langgraph")),
                allowed_tools=list(payload.get("allowedTools", [])),
                max_agent_steps=int(payload.get("maxAgentSteps", 10)),
                max_tool_calls=int(payload.get("maxToolCalls", 10)),
            )
            self.assertEqual(bool(expected.get("allow", False)), decision.allow, msg=name)
            self.assertEqual(str(expected.get("reason", "")), decision.reason, msg=name)


if __name__ == "__main__":
    unittest.main()
