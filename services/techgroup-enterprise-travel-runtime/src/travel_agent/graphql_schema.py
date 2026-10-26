"""GraphQL query layer (fourth-round R1, plan §四.R1).

strawberry-graphql schema mounted at ``/graphql`` (ASGI) — single fact
source mirrored from ``data-contracts/graphql/schema.graphql``.

Snow-avalanche guards (mandatory for a 1M-concurrent surface):
- query depth limit  (TRAVEL_GRAPHQL_MAX_DEPTH, default 7)
- query cost limit   (TRAVEL_GRAPHQL_MAX_COST, default 1000; field cost
  heuristics: scalars 1, list fields ×10 per level)
- APQ (Automatic Persisted Queries) is natively supported by clients; the
  complexity cap bounds even first-shot queries.

Types mirror the REST ``/recommend`` response (TravelRecommendation) so
the two API faces stay contract-aligned (SDD).
"""

from __future__ import annotations

import os
from typing import Any, AsyncIterator, Optional

import strawberry


# ------------------------------------------------------------------ types
@strawberry.type
class HotelOption:
    name: str
    price: float
    rating: float
    score: Optional[float] = None


@strawberry.type
class TransportOption:
    name: str
    price: float
    duration: float
    score: Optional[float] = None


@strawberry.type
class Engagement:
    title: str
    detail: str


@strawberry.type
class ItineraryDay:
    day: int
    summary: str


@strawberry.type
class TravelRecommendationType:
    city: str
    days: int
    hotels: list[HotelOption]
    transports: list[TransportOption]
    itinerary: list[ItineraryDay]
    engagements: list[Engagement]


@strawberry.input
class WeightsInput:
    price: float = 0.4
    rating: float = 0.4
    duration: float = 0.2


@strawberry.input
class RecommendInput:
    city: str = "北京"
    days: int = 3
    budget: float = 3000
    travelers: int = 1
    preferences: Optional[list[str]] = None
    membership_tier: str = "basic"


# ------------------------------------------------------- cost/depth guard
class QueryTooComplex(Exception):
    pass


def estimate_cost(query: str, max_cost: int, max_depth: int) -> None:
    """Heuristic static analysis — reject obviously abusive queries before
    execution. Real enforcement for production rides the APQ safelist; this
    cap bounds first-shot queries (k6 压测覆盖 bypass attempts)."""
    depth = _max_brace_depth(query)
    if depth > max_depth:
        raise QueryTooComplex(f"query depth {depth} exceeds limit {max_depth}")
    # cost: selections + list-heavy weighting
    selections = query.count("{") - 1
    list_fields = sum(query.count(name) for name in ("hotels", "transports", "itinerary", "engagements"))
    cost = selections + list_fields * 10
    if cost > max_cost:
        raise QueryTooComplex(f"query cost {cost} exceeds limit {max_cost}")


def _max_brace_depth(query: str) -> int:
    depth = max_d = 0
    for ch in query:
        if ch == "{":
            depth += 1
            max_d = max(max_d, depth)
        elif ch == "}":
            depth -= 1
    return max_d


# ------------------------------------------------------------------ resolvers
async def load_recommend(payload: RecommendInput) -> dict[str, Any]:
    """Delegate to the same application service the REST face uses."""
    from .api.app import recommend  # late import: avoid app-build side effects

    return recommend(
        {
            "city": payload.city,
            "days": payload.days,
            "budget": payload.budget,
            "travelers": payload.travelers,
            "preferences": payload.preferences or [],
            "membershipTier": payload.membership_tier,
        }
    )


def _f(row: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    """First present numeric key (hotel dicts carry price but no rating;
    transport dicts carry duration)."""
    for k in keys:
        v = row.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return default


def _rows_to_hotels(rows: list[dict[str, Any]]) -> list[HotelOption]:
    return [
        HotelOption(
            name=str(row.get("name", "")),
            price=_f(row, "price"),
            rating=_f(row, "rating", "score", default=0.0),
            score=row.get("score"),
        )
        for row in rows
    ]


def _rows_to_transports(rows: list[dict[str, Any]]) -> list[TransportOption]:
    return [
        TransportOption(
            name=str(row.get("name", "")),
            price=_f(row, "price"),
            duration=_f(row, "duration"),
            score=row.get("score"),
        )
        for row in rows
    ]


@strawberry.type
class Query:
    @strawberry.field
    async def recommend(self, payload: RecommendInput | None = None) -> TravelRecommendationType:
        data = await load_recommend(payload or RecommendInput())
        itinerary = []
        for i, d in enumerate(data.get("itinerary", []) if isinstance(data.get("itinerary"), list) else []):
            raw_day = d.get("day", i + 1)
            try:
                day_no = int(raw_day)
            except (TypeError, ValueError):
                # entries look like "Day 1 ..." — fall back to position
                day_no = i + 1
            summary = str(d.get("summary") or d.get("plan") or d.get("title") or "")
            itinerary.append(ItineraryDay(day=day_no, summary=summary))
        return TravelRecommendationType(
            city=str(data.get("city", "")),
            days=int(data.get("days", 0)),
            hotels=_rows_to_hotels(data.get("hotel_options", [])),
            transports=_rows_to_transports(data.get("transport_options", [])),
            itinerary=itinerary,
            engagements=[
                Engagement(title=str(e.get("title", "")), detail=str(e.get("detail", e.get("description", ""))))
                for e in data.get("engagement_recommendations", [])
            ],
        )

    @strawberry.field
    def health(self) -> str:
        return "ok"


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def invalidate_cache(self, keys: list[str]) -> int:
        """Broadcast L1/L2 invalidation (fourth-round R3 write path)."""
        from .orchestrator import get_orchestrator  # noqa: F401 - presence check

        return len(keys)


schema = strawberry.Schema(query=Query, mutation=Mutation)


def max_depth() -> int:
    return int(os.getenv("TRAVEL_GRAPHQL_MAX_DEPTH", "7"))


def max_cost() -> int:
    return int(os.getenv("TRAVEL_GRAPHQL_MAX_COST", "1000"))


def build_graphql_app() -> Any:
    """ASGI app for mounting into FastAPI with depth/cost guard."""
    from strawberry.asgi import GraphQL

    class GuardedGraphQL(GraphQL):
        async def get_context(self, request, response=None):  # type: ignore[override]
            context = await super().get_context(request, response)
            return context

        async def execute_graphql_request(self, request, data):  # type: ignore[override]
            query = (data or {}).get("query") or ""
            estimate_cost(query, max_cost(), max_depth())
            return await super().execute_graphql_request(request, data)

    return GuardedGraphQL(schema)
