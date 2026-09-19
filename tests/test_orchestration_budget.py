"""Execution budget enforcement tests (real maxAgentSteps/maxToolCalls)."""

from __future__ import annotations

import os
import unittest

from src.travel_agent.orchestration.budget import BudgetExceeded, ExecutionBudget
from src.travel_agent.orchestrator import build_orchestrator
from src.travel_agent.models import TravelRequest


class ExecutionBudgetUnitTestCase(unittest.TestCase):
    def test_tool_call_budget_exhausts(self) -> None:
        budget = ExecutionBudget(max_tool_calls=2)
        budget.consume_tool_call("search_hotels")
        budget.consume_tool_call("search_transports")
        with self.assertRaises(BudgetExceeded):
            budget.consume_tool_call("search_attractions")

    def test_agent_step_budget_exhausts(self) -> None:
        budget = ExecutionBudget(max_agent_steps=1)
        budget.consume_agent_step("route_plan")
        with self.assertRaises(BudgetExceeded):
            budget.consume_agent_step("trip_plan")

    def test_snapshot_records_usage(self) -> None:
        budget = ExecutionBudget(max_agent_steps=5, max_tool_calls=5)
        budget.consume_tool_call("search_hotels")
        budget.consume_agent_step("route_plan")
        snapshot = budget.snapshot()
        self.assertEqual(snapshot["used_tool_calls"], 1)
        self.assertEqual(snapshot["used_agent_steps"], 1)


class OrchestratorBudgetEnforcementTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._prev_transport = os.environ.get("TRAVEL_A2A_TRANSPORT")
        os.environ["TRAVEL_A2A_TRANSPORT"] = "mock-distributed"
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.orchestrator = build_orchestrator(repo_root)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._prev_transport is None:
            os.environ.pop("TRAVEL_A2A_TRANSPORT", None)
        else:
            os.environ["TRAVEL_A2A_TRANSPORT"] = cls._prev_transport
        cls.orchestrator.close()

    def _request(self) -> TravelRequest:
        return TravelRequest(city="北京", days=2, budget=2600, travelers=1, preferences=["budget"])

    def test_tool_call_budget_enforced_during_recommend(self) -> None:
        with self.assertRaises(BudgetExceeded):
            self.orchestrator.recommend_with_controls(
                self._request(),
                max_agent_steps=10,
                max_tool_calls=3,
                allowed_tools=["search_hotels", "search_transports", "search_attractions"],
            )

    def test_agent_step_budget_enforced_during_recommend(self) -> None:
        with self.assertRaises(BudgetExceeded):
            self.orchestrator.recommend_with_controls(
                self._request(),
                max_agent_steps=2,
                max_tool_calls=20,
                allowed_tools=["search_hotels", "search_transports", "search_attractions"],
            )

    def test_sufficient_budget_completes(self) -> None:
        result = self.orchestrator.recommend_with_controls(
            self._request(),
            max_agent_steps=10,
            max_tool_calls=10,
            allowed_tools=["search_hotels", "search_transports", "search_attractions"],
        )
        self.assertTrue(len(result.hotel_options) > 0)


if __name__ == "__main__":
    unittest.main()
