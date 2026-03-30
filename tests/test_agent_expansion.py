"""Module provides service components and helpers."""

import unittest
import os
from pathlib import Path

from src.travel_agent.models import TravelRequest
from src.travel_agent.orchestrator import build_orchestrator


class AgentExpansionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_a2a_transport = os.environ.get("TRAVEL_A2A_TRANSPORT")
        os.environ["TRAVEL_A2A_TRANSPORT"] = "mock-distributed"
        project_root = str(Path(__file__).resolve().parents[1])
        self.orchestrator = build_orchestrator(project_root)

    def tearDown(self) -> None:
        if self._prev_a2a_transport is None:
            if "TRAVEL_A2A_TRANSPORT" in os.environ:
                del os.environ["TRAVEL_A2A_TRANSPORT"]
        else:
            os.environ["TRAVEL_A2A_TRANSPORT"] = self._prev_a2a_transport

    def test_new_agents_registered(self) -> None:
        services = self.orchestrator.registry_center.list_services()
        self.assertIn("food-recommendation-agent", services)
        self.assertIn("local-event-agent", services)
        self.assertIn("loyalty-growth-agent", services)
        self.assertIn("weather-risk-agent", services)
        self.assertIn("ancillary-revenue-agent", services)
        self.assertIn("visa-compliance-agent", services)
        self.assertIn("concierge-agent", services)

    def test_new_tools_registered(self) -> None:
        tools = self.orchestrator.registry_center.list_tools()
        self.assertIn("search_foods", tools)
        self.assertIn("search_events", tools)

    def test_engagement_recommendations_present(self) -> None:
        req = TravelRequest(city="北京", days=2, budget=3000, travelers=1, preferences=["family"])
        result = self.orchestrator.recommend(req)
        self.assertTrue(len(result.engagement_recommendations) >= 4)

    def test_harness_capture_and_replay(self) -> None:
        req = TravelRequest(city="上海", days=2, budget=2800, travelers=1, preferences=["comfort"])
        self.orchestrator.recommend(req)
        replay = self.orchestrator.replay_last_harness_case()
        self.assertTrue(replay.get("ok"))
        value = replay.get("engagement_count", 0)
        count = int(value) if isinstance(value, (int, float, str)) else 0
        self.assertTrue(count >= 4)


if __name__ == "__main__":
    unittest.main()

