"""Application layer: use-case services coordinating domain and infrastructure."""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from ..domain.travel import Budget, HotelOption, TransportOption, TripPlan, TripPlanRepository
from ..infrastructure.repositories import InMemoryTripPlanRepository, SqlAlchemyTripPlanRepository
from ..models import TravelRecommendation, TravelRequest

logger = logging.getLogger("travel_agent.application")


def build_plan_repository() -> TripPlanRepository:
    if os.getenv("TRAVEL_PLAN_REPOSITORY", "memory").strip().lower() == "sqlalchemy":
        return SqlAlchemyTripPlanRepository()
    return InMemoryTripPlanRepository()


class RecommendApplicationService:
    """Use case: plan a trip, persist the aggregate, return the recommendation.

    Persistence failures are logged and swallowed on purpose - a write-model
    outage must not fail the traveler's read path.
    """

    def __init__(self, orchestrator, repository: Optional[TripPlanRepository] = None) -> None:
        self._orchestrator = orchestrator
        self._repository = repository or build_plan_repository()
        self._persist = os.getenv("TRAVEL_PERSIST_TRIP_PLANS", "true").strip().lower() == "true"

    def plan_trip(
        self,
        request: TravelRequest,
        recommendation: TravelRecommendation,
        tenant_id: str = "",
        user_id: str = "",
    ) -> TripPlan:
        plan = TripPlan(
            city=request.city,
            days=request.days,
            budget=Budget(amount=request.budget),
            travelers=request.travelers,
            preferences=list(request.preferences),
            membership_tier=request.membership_tier,
        )
        plan.attach_options(
            hotels=[
                HotelOption(
                    name=item.name,
                    score=float(getattr(item, "score", 0.0) or 0.0),
                    price=float(getattr(item, "price", 0.0) or 0.0),
                    reason=str(getattr(item, "reason", "")),
                )
                for item in recommendation.hotel_options
            ],
            transports=[
                TransportOption(
                    name=item.name,
                    score=float(getattr(item, "score", 0.0) or 0.0),
                    price=float(getattr(item, "price", 0.0) or 0.0),
                    reason=str(getattr(item, "reason", "")),
                )
                for item in recommendation.transport_options
            ],
            itinerary=list(recommendation.itinerary),
        )
        if self._persist:
            try:
                self._repository.save(plan)
            except Exception as error:  # noqa: BLE001 - read path must survive write outage
                logger.warning("trip plan persistence failed (plan stays in-memory of caller): %s", error)
        if tenant_id and user_id:
            logger.info(
                "trip plan persisted plan_id=%s tenant=%s user=%s city=%s",
                plan.plan_id,
                tenant_id,
                user_id,
                plan.city,
            )
        return plan

    def get_plan(self, plan_id: str) -> Optional[TripPlan]:
        return self._repository.get(plan_id)

    def list_recent_plans(self, city: str, limit: int = 10) -> List[TripPlan]:
        return self._repository.list_by_city(city, limit=limit)
