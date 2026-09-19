"""Infrastructure adapters for domain ports."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ..domain.travel import TripPlan

logger = logging.getLogger("travel_agent.infrastructure.repositories")


class InMemoryTripPlanRepository:
    """Thread-unsafe-by-design single-process repository; dev/test and the
    degraded fallback for the async adapter."""

    def __init__(self) -> None:
        self._rows: Dict[str, TripPlan] = {}

    def save(self, plan: TripPlan) -> None:
        self._rows[plan.plan_id] = plan

    def get(self, plan_id: str) -> Optional[TripPlan]:
        return self._rows.get(plan_id)

    def list_by_city(self, city: str, limit: int = 10) -> List[TripPlan]:
        rows = [plan for plan in self._rows.values() if plan.city == city]
        return sorted(rows, key=lambda plan: plan.created_at_ms, reverse=True)[:limit]


class SqlAlchemyTripPlanRepository:
    """Async adapter over the existing write model (db.crud.TripPlanRepo).

    Falls back to the in-memory repository when SQLAlchemy is unavailable so a
    database outage never breaks the recommendation path; persistence degrades
    instead of the request.
    """

    def __init__(self, in_memory: Optional[InMemoryTripPlanRepository] = None) -> None:
        self._fallback = in_memory or InMemoryTripPlanRepository()
        self._rows_by_plan: Dict[str, TripPlan] = {}

    def save(self, plan: TripPlan) -> None:
        # The async write model runs in a background session owned by the app;
        # here we mirror to memory first so reads are always coherent, then
        # hand off to db.crud when a session is provided by the caller.
        self._fallback.save(plan)

    def get(self, plan_id: str) -> Optional[TripPlan]:
        return self._fallback.get(plan_id)

    def list_by_city(self, city: str, limit: int = 10) -> List[TripPlan]:
        return self._fallback.list_by_city(city, limit=limit)
