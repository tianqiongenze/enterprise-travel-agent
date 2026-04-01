"""Module coordinates orchestration flow."""

import os
import unittest
from pathlib import Path

from src.travel_agent.models import TravelRequest
from src.travel_agent.orchestrator import build_orchestrator


class OrchestratorTestCase(unittest.TestCase):
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

    def test_recommend_returns_all_sections(self) -> None:
        request = TravelRequest(city="北京", days=3, budget=3000, travelers=2, preferences=["family", "budget"])
        result = self.orchestrator.recommend(request)
        self.assertTrue(len(result.hotel_options) > 0)
        self.assertTrue(len(result.transport_options) > 0)
        self.assertEqual(len(result.itinerary), 3)

    def test_skills_affect_ranking(self) -> None:
        request_family = TravelRequest(city="北京", days=2, budget=3000, travelers=2, preferences=["family"])
        request_comfort = TravelRequest(city="北京", days=2, budget=3000, travelers=2, preferences=["comfort"])
        family_result = self.orchestrator.recommend(request_family)
        comfort_result = self.orchestrator.recommend(request_comfort)
        self.assertNotEqual(family_result.hotel_options[0].name, comfort_result.hotel_options[0].name)

    def test_mcp_audit_logs_record_calls(self) -> None:
        request = TravelRequest(city="上海", days=2, budget=3200, travelers=1, preferences=["comfort"])
        self.orchestrator.recommend(request)
        tools = [entry["tool"] for entry in self.orchestrator.registry.audit_logs]
        self.assertIn("search_hotels", tools)
        self.assertIn("search_transports", tools)
        self.assertIn("search_attractions", tools)

    def test_a2a_logs_and_registry_exist(self) -> None:
        request = TravelRequest(city="北京", days=2, budget=2600, travelers=1, preferences=["budget"])
        self.orchestrator.recommend(request)
        services = self.orchestrator.registry_center.list_services()
        self.assertIn("manager-agent", services)
        self.assertIn("route-making-agent", services)
        self.assertIn("trip-planner-agent", services)
        self.assertIn("visa-compliance-agent", services)
        self.assertIn("concierge-agent", services)
        self.assertIn("local-lifestyle-agent", services)
        self.assertEqual(len(self.orchestrator.a2a_logs), 2)
        tools = self.orchestrator.registry_center.list_tools()
        self.assertIn("search_hotels", tools)
        self.assertIn("search_transports", tools)
        self.assertIn("search_attractions", tools)
        self.assertIn("search_activities", tools)
        self.assertIn("search_souvenirs", tools)

    def test_local_lifestyle_agent_outputs_activity_and_souvenir(self) -> None:
        request = TravelRequest(city="北京", days=2, budget=3600, travelers=1, preferences=["local-life", "culture"])
        result = self.orchestrator.recommend(request)
        engagement_types = {str(item.get("type", "")) for item in result.engagement_recommendations if isinstance(item, dict)}
        self.assertIn("activity", engagement_types)
        self.assertIn("souvenir", engagement_types)

    def test_memory_records_requests(self) -> None:
        request = TravelRequest(city="北京", days=2, budget=2600, travelers=1, preferences=["budget"])
        key = "tenant-1:user-1:conv-1"
        before = self.orchestrator.read_memory(key)
        self.assertEqual(before, [])
        self.orchestrator.recommend_with_memory(request, key)
        after = self.orchestrator.read_memory(key)
        self.assertTrue(len(after) >= 2)

    def test_vector_query_returns_related_messages(self) -> None:
        previous = os.environ.get("TRAVEL_MEMORY_BACKEND")
        os.environ["TRAVEL_MEMORY_BACKEND"] = "vector"
        project_root = str(Path(__file__).resolve().parents[1])
        orchestrator = build_orchestrator(project_root)
        request = TravelRequest(city="上海", days=2, budget=2800, travelers=1, preferences=["comfort"])
        key = "tenant-1:user-2:conv-vector"
        orchestrator.recommend_with_memory(request, key)
        hits = orchestrator.query_memory(key, "上海", limit=2)
        self.assertTrue(len(hits) >= 1)
        if previous is None:
            del os.environ["TRAVEL_MEMORY_BACKEND"]
        else:
            os.environ["TRAVEL_MEMORY_BACKEND"] = previous

    def test_rocksdb_backend_requires_explicit_dependency_and_path(self) -> None:
        previous = os.environ.get("TRAVEL_MEMORY_BACKEND")
        previous_path = os.environ.get("TRAVEL_ROCKSDB_PATH")
        os.environ["TRAVEL_MEMORY_BACKEND"] = "rocksdb"
        project_root = str(Path(__file__).resolve().parents[1])
        if "TRAVEL_ROCKSDB_PATH" in os.environ:
            del os.environ["TRAVEL_ROCKSDB_PATH"]
        with self.assertRaises(RuntimeError):
            build_orchestrator(project_root)

        if previous is None:
            del os.environ["TRAVEL_MEMORY_BACKEND"]
        else:
            os.environ["TRAVEL_MEMORY_BACKEND"] = previous
        if previous_path is None:
            if "TRAVEL_ROCKSDB_PATH" in os.environ:
                del os.environ["TRAVEL_ROCKSDB_PATH"]
        else:
            os.environ["TRAVEL_ROCKSDB_PATH"] = previous_path

    def test_etcd_dual_stack_defaults_to_legacy_mode(self) -> None:
        from src.travel_agent.discovery.real_etcd_registry import RealEtcdRegistry

        previous_host = os.environ.get("ETCD_HOST")
        previous_mode = os.environ.get("TRAVEL_ETCD_CLIENT_MODE")
        os.environ["ETCD_HOST"] = "localhost"
        if "TRAVEL_ETCD_CLIENT_MODE" in os.environ:
            del os.environ["TRAVEL_ETCD_CLIENT_MODE"]

        registry = RealEtcdRegistry()
        self.assertIn(registry._selected_mode, ["legacy", "new", ""])

        if previous_host is None:
            del os.environ["ETCD_HOST"]
        else:
            os.environ["ETCD_HOST"] = previous_host
        if previous_mode is None:
            if "TRAVEL_ETCD_CLIENT_MODE" in os.environ:
                del os.environ["TRAVEL_ETCD_CLIENT_MODE"]
        else:
            os.environ["TRAVEL_ETCD_CLIENT_MODE"] = previous_mode

    def test_etcd_dual_stack_rejects_unknown_mode(self) -> None:
        from src.travel_agent.discovery.real_etcd_registry import RealEtcdRegistry

        previous_host = os.environ.get("ETCD_HOST")
        previous_mode = os.environ.get("TRAVEL_ETCD_CLIENT_MODE")
        os.environ["ETCD_HOST"] = "localhost"
        os.environ["TRAVEL_ETCD_CLIENT_MODE"] = "unknown"

        with self.assertRaises(RuntimeError):
            RealEtcdRegistry()

        if previous_host is None:
            del os.environ["ETCD_HOST"]
        else:
            os.environ["ETCD_HOST"] = previous_host
        if previous_mode is None:
            del os.environ["TRAVEL_ETCD_CLIENT_MODE"]
        else:
            os.environ["TRAVEL_ETCD_CLIENT_MODE"] = previous_mode

    def test_controlled_recommend_rejects_insufficient_tools(self) -> None:
        request = TravelRequest(city="北京", days=2, budget=2600, travelers=1, preferences=["budget"])
        with self.assertRaises(ValueError):
            self.orchestrator.recommend_with_controls(
                request=request,
                max_agent_steps=10,
                max_tool_calls=10,
                allowed_tools=["search_hotels"],
            )


if __name__ == "__main__":
    unittest.main()
