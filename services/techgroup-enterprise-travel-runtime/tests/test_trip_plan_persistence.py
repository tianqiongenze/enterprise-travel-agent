"""Integration: TripPlan aggregate persistence + domain-event recording.

Covers the Gap2 acceptance: save -> fresh-repository load equivalence,
domain events recorded onto the event bus (JSONL evidence), and a second
read that survives a "restart" (new repository instance over the same DB).
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("TRAVEL_EVENT_BUS", "local")

from src.travel_agent.application.recommend_service import RecommendApplicationService
from src.travel_agent.db.database import build_engine, build_session_factory
from src.travel_agent.domain.travel import Budget, TripPlan
from src.travel_agent.events.consumer import _JsonlWriter
from src.travel_agent.infrastructure.repositories import SqlAlchemyTripPlanRepository
from src.travel_agent.models import RecommendationItem, TravelRecommendation, TravelRequest


class _RecordingBus:
    """Minimal in-memory bus double that records like production writers."""

    def __init__(self, out_dir: Path) -> None:
        self.published: list[tuple[str, dict]] = []
        os.environ["TRAVEL_EVENT_OUT_DIR"] = str(out_dir)
        self._writer = _JsonlWriter("plan_domain_events.jsonl")
        os.environ.pop("TRAVEL_EVENT_OUT_DIR", None)

    def publish(self, topic: str, payload: dict) -> None:
        self.published.append((topic, payload))
        self._writer.write({"topic": topic, "payload": payload})


class TripPlanPersistenceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_file = Path(self._tmp.name) / "plans.db"
        self.events_dir = Path(self._tmp.name) / "events"
        self.engine = build_engine(f"sqlite+aiosqlite:///{self.db_file.as_posix()}")
        from src.travel_agent.db import models as db_models

        async def _create_all() -> None:
            async with self.engine.begin() as conn:
                await conn.run_sync(db_models.Base.metadata.create_all)

        asyncio.run(_create_all())
        self.session_factory = build_session_factory(self.engine)
        # LIFO: dispose runs before the tempdir cleanup, so Windows can delete plans.db.
        self.addCleanup(self._dispose_engine)

    def _dispose_engine(self) -> None:
        try:
            asyncio.run(self.engine.dispose())
        except Exception:
            pass

    def _fresh_repository(self) -> SqlAlchemyTripPlanRepository:
        return SqlAlchemyTripPlanRepository(session_factory=self.session_factory)

    def _service(self, bus: _RecordingBus) -> RecommendApplicationService:
        from src.travel_agent.orchestrator import TravelOrchestrator  # noqa: F401 - import sanity

        return RecommendApplicationService(orchestrator=None, repository=self._fresh_repository(), event_bus=bus)

    def _recommendation(self) -> TravelRecommendation:
        return TravelRecommendation(
            hotel_options=[
                RecommendationItem(id="h1", name="西湖国宾馆", score=0.92, price=1200.0, tags=["湖景"], reason="湖景")
            ],
            transport_options=[],
            itinerary=[{"day": "1", "plan": "西湖"}, {"day": "2", "plan": "灵隐寺"}],
        )

    def test_save_then_fresh_repository_load_is_equivalent(self) -> None:
        bus = _RecordingBus(self.events_dir)
        service = self._service(bus)
        plan = service.plan_trip(TravelRequest(city="杭州", days=2, budget=3000.0, travelers=2), self._recommendation())

        reloaded = self._fresh_repository().get(plan.plan_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.plan_id, plan.plan_id)
        self.assertEqual(reloaded.city, plan.city)
        self.assertEqual(reloaded.days, plan.days)
        self.assertEqual(len(reloaded.hotel_options), len(plan.hotel_options))
        self.assertEqual(reloaded.hotel_options[0].name, plan.hotel_options[0].name)
        self.assertEqual(reloaded.itinerary, plan.itinerary)

    def test_domain_events_recorded_via_event_out_dir(self) -> None:
        bus = _RecordingBus(self.events_dir)
        service = self._service(bus)
        plan = service.plan_trip(TravelRequest(city="杭州", days=2, budget=3000.0, travelers=2), self._recommendation())

        topics = [topic for topic, _ in bus.published]
        self.assertIn("travel.plan.domain-events", topics)
        payloads = [payload for topic, payload in bus.published if topic == "travel.plan.domain-events"]
        self.assertTrue(any(p["event"] == "TripPlanCreated" and p["plan_id"] == plan.plan_id for p in payloads))
        self.assertTrue(any(p["event"] == "TripPlanOptionsAttached" for p in payloads))

        jsonl_files = sorted(self.events_dir.glob("*.jsonl"))
        self.assertTrue(jsonl_files, "expected JSONL evidence under TRAVEL_EVENT_OUT_DIR-style dir")
        lines = [json.loads(line) for line in jsonl_files[0].read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(any(entry["payload"].get("event") == "TripPlanCreated" for entry in lines))

    def test_second_read_survives_restart(self) -> None:
        bus = _RecordingBus(self.events_dir)
        service = self._service(bus)
        plan = service.plan_trip(TravelRequest(city="杭州", days=2, budget=3000.0, travelers=2), self._recommendation())

        # "Restart": brand-new repository instances over the same DB file.
        first = self._fresh_repository().get(plan.plan_id)
        second = self._fresh_repository().get(plan.plan_id)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.plan_id, second.plan_id)
        self.assertEqual(first.city, second.city)

        # Rehydrated aggregate must not re-emit TripPlanCreated.
        self.assertEqual([e["event"] for e in second.events if e["event"] == "TripPlanCreated"].count("TripPlanCreated"), 1)

    def test_in_memory_aggregate_roundtrip_directly(self) -> None:
        repo = self._fresh_repository()
        plan = TripPlan(city="北京", days=3, budget=Budget(amount=5000.0), travelers=2, membership_tier="gold")
        repo.save(plan)
        loaded = repo.get(plan.plan_id)
        self.assertEqual(loaded.membership_tier, "gold")
        self.assertEqual(loaded.events[0]["event"], "TripPlanCreated")


if __name__ == "__main__":
    unittest.main()
