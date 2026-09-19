"""DDD domain layer tests: aggregate invariants, ports, application service."""

from __future__ import annotations

import unittest

from src.travel_agent.application.recommend_service import RecommendApplicationService
from src.travel_agent.domain.travel import (
    Budget,
    HotelOption,
    Preference,
    TransportOption,
    TripPlan,
)
from src.travel_agent.infrastructure.repositories import InMemoryTripPlanRepository
from src.travel_agent.models import TravelRecommendation, TravelRequest


class TripPlanAggregateTestCase(unittest.TestCase):
    def test_invariants_reject_invalid_plan(self) -> None:
        with self.assertRaises(ValueError):
            TripPlan(city="", days=3, budget=Budget(1000))
        with self.assertRaises(ValueError):
            TripPlan(city="北京", days=45, budget=Budget(1000))
        with self.assertRaises(ValueError):
            TripPlan(city="北京", days=3, budget=Budget(-5))
        with self.assertRaises(ValueError):
            TripPlan(city="北京", days=3, budget=Budget(1000), travelers=0)

    def test_confirm_requires_options(self) -> None:
        plan = TripPlan(city="北京", days=3, budget=Budget(3000), preferences=[Preference("family")])
        with self.assertRaises(ValueError):
            plan.confirm()
        plan.attach_options(
            hotels=[HotelOption(name="H1", score=4.5, price=500)],
            transports=[TransportOption(name="T1", score=4.0, price=200)],
            itinerary=[{"day": 1, "spot": "故宫"}],
        )
        plan.confirm()
        self.assertEqual(plan.status, "confirmed")
        self.assertTrue(any(e["event"] == "TripPlanConfirmed" for e in plan.events))
        self.assertEqual(plan.to_summary()["hotel_count"], 1)


class TripPlanRepositoryTestCase(unittest.TestCase):
    def test_in_memory_repository_roundtrip(self) -> None:
        repo = InMemoryTripPlanRepository()
        plan = TripPlan(city="上海", days=2, budget=Budget(2600))
        plan.attach_options([HotelOption(name="H")], [TransportOption(name="T")], [])
        repo.save(plan)
        self.assertEqual(repo.get(plan.plan_id).city, "上海")
        self.assertEqual(len(repo.list_by_city("上海")), 1)
        self.assertEqual(repo.list_by_city("北京"), [])


class RecommendApplicationServiceTestCase(unittest.TestCase):
    def test_plan_trip_maps_recommendation_to_aggregate(self) -> None:
        service = RecommendApplicationService(orchestrator=None, repository=InMemoryTripPlanRepository())
        request = TravelRequest(city="北京", days=2, budget=2600, travelers=1, preferences=["budget"])
        recommendation = TravelRecommendation(
            hotel_options=[],
            transport_options=[],
            itinerary=[],
            engagement_recommendations=[],
        )
        recommendation.hotel_options.append(type("H", (), {"name": "酒店A", "score": 4.6, "price": 560, "reason": "高性价比"})())
        recommendation.transport_options.append(type("T", (), {"name": "高铁", "score": 4.2, "price": 300, "reason": "快"})())
        plan = service.plan_trip(request, recommendation, tenant_id="tenant-1", user_id="user-1")
        self.assertEqual(plan.city, "北京")
        self.assertEqual(len(plan.hotel_options), 1)
        self.assertEqual(plan.to_summary()["transport_count"], 1)
        self.assertIsNotNone(service.get_plan(plan.plan_id))


if __name__ == "__main__":
    unittest.main()
