"""Module provides service components and helpers."""

import os
import unittest
from pathlib import Path

from src.travel_agent.models import TravelRequest
from src.travel_agent.orchestrator import build_orchestrator


class OrchestrationEngineModesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_a2a_transport = os.environ.get("TRAVEL_A2A_TRANSPORT")
        os.environ["TRAVEL_A2A_TRANSPORT"] = "mock-distributed"

    def tearDown(self) -> None:
        if self._prev_a2a_transport is None:
            if "TRAVEL_A2A_TRANSPORT" in os.environ:
                del os.environ["TRAVEL_A2A_TRANSPORT"]
        else:
            os.environ["TRAVEL_A2A_TRANSPORT"] = self._prev_a2a_transport

    def test_default_mode_is_langgraph(self) -> None:
        previous = os.environ.get("TRAVEL_ORCHESTRATION_ENGINE")
        if "TRAVEL_ORCHESTRATION_ENGINE" in os.environ:
            del os.environ["TRAVEL_ORCHESTRATION_ENGINE"]
        self._assert_engine_in_event("langgraph", "langgraph")
        if previous is not None:
            os.environ["TRAVEL_ORCHESTRATION_ENGINE"] = previous

    def test_langgraph_mode_emits_engine_event(self) -> None:
        self._assert_mode_event("langgraph", "langgraph")

    def test_agentscope_mode_emits_engine_event(self) -> None:
        self._assert_mode_event("agentscope", "agentscope-ai")

    def test_oneagents_mode_emits_engine_event(self) -> None:
        self._assert_mode_event("oneagents", "oneagents")

    def test_shadow_engine_emits_comparison_event(self) -> None:
        previous_mode = os.environ.get("TRAVEL_ORCHESTRATION_ENGINE")
        previous_shadow = os.environ.get("TRAVEL_ORCHESTRATION_SHADOW_ENGINE")
        os.environ["TRAVEL_ORCHESTRATION_ENGINE"] = "langgraph"
        os.environ["TRAVEL_ORCHESTRATION_SHADOW_ENGINE"] = "agentscope"

        self._assert_engine_in_event("langgraph", "langgraph")

        project_root = str(Path(__file__).resolve().parents[1])
        orchestrator = build_orchestrator(project_root)
        req = TravelRequest(city="北京", days=2, budget=2600, travelers=1, preferences=["family"])
        orchestrator.recommend(req)
        events = getattr(orchestrator.event_bus, "events", [])
        shadow_events = [item for item in events if isinstance(item, dict) and item.get("topic") == "recommend.engine_shadow_compared"]
        self.assertTrue(len(shadow_events) >= 1)

        if previous_mode is None:
            del os.environ["TRAVEL_ORCHESTRATION_ENGINE"]
        else:
            os.environ["TRAVEL_ORCHESTRATION_ENGINE"] = previous_mode
        if previous_shadow is None:
            del os.environ["TRAVEL_ORCHESTRATION_SHADOW_ENGINE"]
        else:
            os.environ["TRAVEL_ORCHESTRATION_SHADOW_ENGINE"] = previous_shadow

    def test_local_mode_falls_back_to_langgraph(self) -> None:
        previous_mode = os.environ.get("TRAVEL_ORCHESTRATION_ENGINE")
        previous_fallback = os.environ.get("TRAVEL_ORCHESTRATION_FALLBACK_ENGINE")
        os.environ["TRAVEL_ORCHESTRATION_ENGINE"] = "local"
        os.environ["TRAVEL_ORCHESTRATION_FALLBACK_ENGINE"] = "langgraph"
        project_root = str(Path(__file__).resolve().parents[1])
        orchestrator = build_orchestrator(project_root)
        req = TravelRequest(city="上海", days=2, budget=3000, travelers=1, preferences=["comfort"])
        orchestrator.recommend(req)
        events = getattr(orchestrator.event_bus, "events", [])
        engine_events = [item for item in events if isinstance(item, dict) and item.get("topic") == "recommend.engine_selected"]
        self.assertTrue(len(engine_events) >= 1)
        payload = engine_events[-1].get("payload", {})
        self.assertEqual(payload.get("engine"), "langgraph")
        if previous_mode is None:
            del os.environ["TRAVEL_ORCHESTRATION_ENGINE"]
        else:
            os.environ["TRAVEL_ORCHESTRATION_ENGINE"] = previous_mode
        if previous_fallback is None:
            del os.environ["TRAVEL_ORCHESTRATION_FALLBACK_ENGINE"]
        else:
            os.environ["TRAVEL_ORCHESTRATION_FALLBACK_ENGINE"] = previous_fallback

    def _assert_mode_event(self, mode: str, adapter_name: str) -> None:
        previous = os.environ.get("TRAVEL_ORCHESTRATION_ENGINE")
        os.environ["TRAVEL_ORCHESTRATION_ENGINE"] = mode

        self._assert_engine_in_event(mode, adapter_name)

        if previous is None:
            del os.environ["TRAVEL_ORCHESTRATION_ENGINE"]
        else:
            os.environ["TRAVEL_ORCHESTRATION_ENGINE"] = previous

    def _assert_engine_in_event(self, mode: str, adapter_name: str) -> None:

        project_root = str(Path(__file__).resolve().parents[1])
        orchestrator = build_orchestrator(project_root)
        req = TravelRequest(city="上海", days=2, budget=3200, travelers=1, preferences=["comfort"])
        orchestrator.recommend(req)

        events = getattr(orchestrator.event_bus, "events", [])
        topics = [item.get("topic") for item in events if isinstance(item, dict)]
        self.assertIn("recommend.engine_selected", topics)
        engine_events = [item for item in events if isinstance(item, dict) and item.get("topic") == "recommend.engine_selected"]
        self.assertTrue(len(engine_events) >= 1)
        payload = engine_events[-1].get("payload", {})
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        self.assertEqual(payload.get("engine"), mode)
        self.assertEqual(metadata.get("adapter"), adapter_name)

        


if __name__ == "__main__":
    unittest.main()

