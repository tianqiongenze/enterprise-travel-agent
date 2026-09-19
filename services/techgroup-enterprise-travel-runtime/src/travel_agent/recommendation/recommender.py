"""Module provides service components and helpers."""

from collections.abc import Mapping
from typing import Any, TYPE_CHECKING, cast

from ..memory.graphrag import GraphRAGContextBuilder
from ..models import RecommendationItem, TravelRequest
from .go_ranker_client import GoRankerClient
from .scoring import hotel_score, transport_score

if TYPE_CHECKING:
    from ..mcp.registry import MCPToolRegistry


class TravelRecommender:
    def __init__(self, tool_registry: "MCPToolRegistry") -> None:
        self.tool_registry: MCPToolRegistry = tool_registry
        self.go_ranker: GoRankerClient = GoRankerClient()
        self.graphrag: GraphRAGContextBuilder = GraphRAGContextBuilder()

    def recommend_hotels(self, request: TravelRequest, weights: dict[str, float]) -> list[RecommendationItem]:
        rows = self._rows_from_tool(self.tool_registry.call("search_hotels", city=request.city))
        payloads = [
            {
                "price": row["price"],
                "rating": row["rating"],
                "duration": 0.0,
                "tags": row["tags"],
                "budget": request.budget,
                "weights": weights,
            }
            for row in rows
        ]
        batch_scores = self.go_ranker.score_batch("hotel", payloads)
        scored: list[RecommendationItem] = []
        for idx, row in enumerate(rows):
            score = None
            if batch_scores is not None and idx < len(batch_scores):
                score = batch_scores[idx]
            if score is None:
                score = self.go_ranker.score_hotel(row["price"], row["rating"], row["tags"], request.budget, weights)
            if score is None:
                score = hotel_score(row["price"], row["rating"], row["tags"], request.budget, weights)
                self.go_ranker.shadow_compare(
                    "hotel",
                    payloads[idx],
                    score,
                )
            reason = "价格/评分/偏好标签综合最优"
            scored.append(
                RecommendationItem(
                    id=row["id"],
                    name=row["name"],
                    score=round(score, 4),
                    price=row["price"],
                    tags=row["tags"],
                    reason=reason,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:3]

    def recommend_transports(self, request: TravelRequest, weights: dict[str, float]) -> list[RecommendationItem]:
        rows = self._rows_from_tool(self.tool_registry.call("search_transports", city=request.city))
        scored: list[RecommendationItem] = []
        per_capita_budget = request.budget / max(request.travelers, 1)
        payloads = [
            {
                "price": row["price"],
                "rating": 0.0,
                "duration": row["duration"],
                "tags": row["tags"],
                "budget": per_capita_budget,
                "weights": weights,
            }
            for row in rows
        ]
        batch_scores = self.go_ranker.score_batch("transport", payloads)
        for idx, row in enumerate(rows):
            score = None
            if batch_scores is not None and idx < len(batch_scores):
                score = batch_scores[idx]
            if score is None:
                score = self.go_ranker.score_transport(row["price"], row["duration"], row["tags"], per_capita_budget, weights)
            if score is None:
                score = transport_score(row["price"], row["duration"], row["tags"], per_capita_budget, weights)
                self.go_ranker.shadow_compare(
                    "transport",
                    payloads[idx],
                    score,
                )
            reason = "时效/成本/偏好标签综合最优"
            scored.append(
                RecommendationItem(
                    id=row["id"],
                    name=row["name"],
                    score=round(score, 4),
                    price=row["price"],
                    tags=row["tags"],
                    reason=reason,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:3]

    def recommend_itinerary(
        self,
        request: TravelRequest,
        hotels: list[RecommendationItem],
        transports: list[RecommendationItem],
    ) -> list[dict[str, str]]:
        rows = self._rows_from_tool(self.tool_registry.call("search_attractions", city=request.city))
        graph_hints = set(self.graphrag.build_hints(rows, request.preferences, limit=8))
        ranked_attractions = sorted(rows, key=lambda item: self._preference_hit(item.get("tags", []), request.preferences), reverse=True)
        ranked_attractions.sort(
            key=lambda item: 1 if str(item.get("name", "")) in graph_hints else 0,
            reverse=True,
        )
        itinerary: list[dict[str, str]] = []
        best_hotel = hotels[0].name if hotels else "待定酒店"
        best_transport = transports[0].name if transports else "待定交通"
        for day in range(1, request.days + 1):
            attraction = ranked_attractions[(day - 1) % max(1, len(ranked_attractions))] if ranked_attractions else {"name": "城市漫步"}
            itinerary.append(
                {
                    "day": "Day %s" % day,
                    "morning": "入住/整备：%s" % best_hotel if day == 1 else "城市探索",
                    "afternoon": "景点：%s" % attraction["name"],
                    "evening": "交通建议：%s" % best_transport if day == request.days else "自由活动",
                }
            )
        return itinerary

    def recommend_foods(self, request: TravelRequest) -> list[dict[str, object]]:
        if "search_foods" not in self.tool_registry.list_tools():
            return []
        rows = self._rows_from_tool(self.tool_registry.call("search_foods", city=request.city))
        dict_rows = [dict(row) for row in rows]
        ranked = sorted(dict_rows, key=lambda item: self._preference_hit(item.get("tags", []), request.preferences), reverse=True)
        return [dict(row) for row in ranked[:3]]

    def recommend_events(self, request: TravelRequest) -> list[dict[str, object]]:
        if "search_events" not in self.tool_registry.list_tools():
            return []
        rows = self._rows_from_tool(self.tool_registry.call("search_events", city=request.city))
        dict_rows = [dict(row) for row in rows]
        ranked = sorted(dict_rows, key=lambda item: self._preference_hit(item.get("tags", []), request.preferences), reverse=True)
        return [dict(row) for row in ranked[:3]]

    def recommend_activities(self, request: TravelRequest) -> list[dict[str, object]]:
        return self._recommend_local_items(request, "search_activities")

    def recommend_souvenirs(self, request: TravelRequest) -> list[dict[str, object]]:
        return self._recommend_local_items(request, "search_souvenirs")

    def _recommend_local_items(self, request: TravelRequest, tool_name: str) -> list[dict[str, object]]:
        if tool_name not in self.tool_registry.list_tools():
            return []
        rows = self._rows_from_tool(self.tool_registry.call(tool_name, city=request.city))
        dict_rows = [dict(row) for row in rows]
        ranked = sorted(dict_rows, key=lambda item: self._preference_hit(item.get("tags", []), request.preferences), reverse=True)
        return [dict(row) for row in ranked[:3]]

    def _preference_hit(self, tags: list[str], preferences: list[str]) -> int:
        if not preferences:
            return 0
        return len(set(tags).intersection(set(preferences)))

    def _rows_from_tool(self, rows: object) -> list[dict[str, Any]]:
        if not isinstance(rows, list):
            return []
        normalized: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, Mapping):
                normalized.append(dict(cast(Mapping[str, Any], row)))
        return normalized
