"""TDD tests for the GraphQL layer (fourth-round R1)."""

from __future__ import annotations

import pytest

strawberry = pytest.importorskip("strawberry")

from src.travel_agent.graphql_schema import (  # noqa: E402
    QueryTooComplex,
    RecommendInput,
    Query,
    estimate_cost,
    schema,
)


def test_schema_matches_contract_shape():
    sdl = str(schema)
    for required in ("recommend", "TravelRecommendation", "HotelOption", "TransportOption", "invalidateCache"):
        assert required in sdl, f"contract drift: {required} missing from schema"


@pytest.mark.asyncio
async def test_recommend_query_executes(monkeypatch):
    fake = {
        "city": "北京",
        "days": 3,
        "hotel_options": [{"name": "H", "price": 800.0, "rating": 4.5}],
        "transport_options": [],
        "itinerary": [{"day": 1, "summary": "s"}],
        "engagement_recommendations": [{"title": "t", "detail": "d"}],
    }
    import src.travel_agent.graphql_schema as g

    async def fake_load(payload):
        return fake

    monkeypatch.setattr(g, "load_recommend", fake_load)
    result = await schema.execute(
        query="""
        query { recommend(payload: {city: "北京"}) {
            city days
            hotels { name price rating }
            itinerary { day summary }
        } }
        """
    )
    assert result.errors is None
    assert result.data["recommend"]["city"] == "北京"
    assert result.data["recommend"]["hotels"][0]["name"] == "H"


def test_depth_guard_rejects_deep_queries():
    deep = "query { " + "a { " * 10 + "b " + "} }" * 10
    with pytest.raises(QueryTooComplex):
        estimate_cost(deep, max_cost=1000, max_depth=7)


def test_cost_guard_rejects_list_bombs():
    heavy = "query { r { hotels { n } transports { n } itinerary { n } engagements { n } } }"
    with pytest.raises(QueryTooComplex):
        estimate_cost(heavy, max_cost=10, max_depth=7)


def test_normal_query_passes_guard():
    ok = 'query { recommend(payload: {city: "北京"}) { city hotels { name } } }'
    estimate_cost(ok, max_cost=1000, max_depth=7)  # no raise


def test_recommend_input_defaults():
    payload = RecommendInput()
    assert payload.city == "北京" and payload.days == 3 and payload.membership_tier == "basic"
