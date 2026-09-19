"""Coordinates orchestration flow: engines, A2A round trips, budgets, memory."""

import os
import json
from typing import Dict, List, Optional

from .a2a.router import A2ARouter
from .a2a.worker import A2AWorker
from .agents.llm import LlmRationaleDecorator, create_rationale_provider
from .agents.manager_agent import (
    AncillaryRevenueAgent,
    ConciergeAgent,
    FoodRecommendationAgent,
    LocalEventAgent,
    LocalLifestyleAgent,
    LoyaltyGrowthAgent,
    ManagerAgent,
    RouteMakingAgent,
    TripPlannerAgent,
    VisaComplianceAgent,
    WeatherRiskAgent,
)
from .discovery.factory import build_registry_from_env
from .events.bus import build_event_bus_from_env
from .mcp.registry import MCPToolRegistry
from .memory.in_memory import InMemoryStore
from .memory.rocksdb_store import RocksDBMemoryStore
from .memory.redis_store import RedisMemoryStore
from .memory.vector_store import VectorMemoryStore
from .models import TravelRecommendation, TravelRequest
from .recommendation.recommender import TravelRecommender
from .orchestration.engine import build_engine_by_name, build_engine_from_env
from .orchestration.budget import (
    ExecutionBudget,
    reset_current_budget,
    set_current_budget,
)
from .harness.replay import OrchestrationHarness
from .skills.loader import SkillLoader
from .tools.data_store import DataStore


def _bounded_append(rows: List[Dict[str, object]], item: Dict[str, object], max_len: int) -> None:
    rows.append(item)
    overflow = len(rows) - max_len
    if overflow > 0:
        del rows[:overflow]


def build_orchestrator(project_root: str) -> "TravelOrchestrator":
    return TravelOrchestrator(
        data_dir=os.path.join(project_root, "data"),
        skills_dir=os.path.join(project_root, "skills"),
    )


class TravelOrchestrator:
    def __init__(self, data_dir: str, skills_dir: str) -> None:
        self.runtime_endpoint = os.getenv("TRAVEL_RUNTIME_ENDPOINT", "http://127.0.0.1:8000")
        self.registry_center = build_registry_from_env()
        self.event_bus = build_event_bus_from_env()
        self.data_store = DataStore(data_dir)
        self.skill_loader = SkillLoader(skills_dir)
        self.registry = MCPToolRegistry(self.registry_center)
        self.a2a_router = A2ARouter()
        self.a2a_logs: List[Dict[str, object]] = []
        self.max_a2a_logs = int(os.getenv("TRAVEL_A2A_LOG_MAX_RECORDS", "200"))
        self.harness = OrchestrationHarness(max_records=int(os.getenv("TRAVEL_HARNESS_MAX_RECORDS", "50")))
        self.memory_store = self._build_memory_store()
        self._register_agents()
        self._register_tools()
        self.recommender = TravelRecommender(self.registry)
        self.manager = ManagerAgent(
            RouteMakingAgent(self.recommender),
            TripPlannerAgent(self.recommender),
            FoodRecommendationAgent(self.recommender),
            LocalEventAgent(self.recommender),
            LoyaltyGrowthAgent(),
            WeatherRiskAgent(),
            AncillaryRevenueAgent(),
            VisaComplianceAgent(),
            ConciergeAgent(),
            LocalLifestyleAgent(self.recommender),
            rationale_decorator=LlmRationaleDecorator(create_rationale_provider()),
        )
        self.engine = build_engine_from_env(self.manager)
        self.shadow_engine_mode = os.getenv("TRAVEL_ORCHESTRATION_SHADOW_ENGINE", "").strip().lower()
        self.a2a_worker = A2AWorker(self.a2a_router)
        self.a2a_replies_enabled = os.getenv("TRAVEL_A2A_REPLIES", "true").strip().lower() == "true"
        self._register_a2a_handlers()

    def _register_a2a_handlers(self) -> None:
        """Handlers execute agent tasks when A2A tasks are drained (infra-level
        data access, deliberately outside the caller's MCP tool budget)."""

        def route_plan(payload: Dict[str, object]) -> Dict[str, object]:
            city = str(payload.get("city", ""))
            hotels = self.data_store.hotels_by_city(city)
            transports = self.data_store.transports_by_city(city)
            return {
                "city": city,
                "hotel_count": len(hotels),
                "transport_count": len(transports),
                "status": "completed",
            }

        def trip_plan(payload: Dict[str, object]) -> Dict[str, object]:
            days = int(payload.get("days", 0) or 0)
            return {"days": days, "status": "acknowledged", "planner": "trip-planner-agent"}

        self.a2a_worker.register_handler("route-making-agent", "route_plan", route_plan)
        self.a2a_worker.register_handler("trip-planner-agent", "trip_plan", trip_plan)

    def _build_memory_store(self):
        backend = os.getenv("TRAVEL_MEMORY_BACKEND", "memory").strip().lower()
        if backend in {"", "memory", "in-memory", "inmemory"}:
            return InMemoryStore()
        if backend == "redis":
            store = RedisMemoryStore()
            if not store.enabled:
                raise RuntimeError("TRAVEL_MEMORY_BACKEND=redis requires REDIS_URL and redis package")
            return store
        if backend == "rocksdb":
            return RocksDBMemoryStore()
        if backend == "vector":
            return VectorMemoryStore()
        raise RuntimeError("Unsupported TRAVEL_MEMORY_BACKEND: %s" % backend)

    def _register_agents(self) -> None:
        self.registry_center.register("manager-agent", self.runtime_endpoint + "/agent/manager")
        self.registry_center.register("route-making-agent", self.runtime_endpoint + "/agent/route")
        self.registry_center.register("trip-planner-agent", self.runtime_endpoint + "/agent/trip")
        self.registry_center.register("food-recommendation-agent", self.runtime_endpoint + "/agent/food")
        self.registry_center.register("local-event-agent", self.runtime_endpoint + "/agent/event")
        self.registry_center.register("local-lifestyle-agent", self.runtime_endpoint + "/agent/lifestyle")
        self.registry_center.register("loyalty-growth-agent", self.runtime_endpoint + "/agent/growth")
        self.registry_center.register("weather-risk-agent", self.runtime_endpoint + "/agent/weather")
        self.registry_center.register("ancillary-revenue-agent", self.runtime_endpoint + "/agent/ancillary")
        self.registry_center.register("visa-compliance-agent", self.runtime_endpoint + "/agent/visa")
        self.registry_center.register("concierge-agent", self.runtime_endpoint + "/agent/concierge")

    def _register_tools(self) -> None:
        self.registry.register("search_hotels", self._search_hotels)
        self.registry.register("search_transports", self._search_transports)
        self.registry.register("search_attractions", self._search_attractions)
        self.registry.register("search_foods", self._search_foods)
        self.registry.register("search_events", self._search_events)
        self.registry.register("search_activities", self._search_activities)
        self.registry.register("search_souvenirs", self._search_souvenirs)

    def _search_hotels(self, city: str) -> List[Dict[str, object]]:
        return [dict(row) for row in self.data_store.hotels_by_city(city)]

    def _search_transports(self, city: str) -> List[Dict[str, object]]:
        return [dict(row) for row in self.data_store.transports_by_city(city)]

    def _search_attractions(self, city: str) -> List[Dict[str, object]]:
        return [dict(row) for row in self.data_store.attractions_by_city(city)]

    def _search_foods(self, city: str) -> List[Dict[str, object]]:
        return [dict(row) for row in self.data_store.foods_by_city(city)]

    def _search_events(self, city: str) -> List[Dict[str, object]]:
        return [dict(row) for row in self.data_store.events_by_city(city)]

    def _search_activities(self, city: str) -> List[Dict[str, object]]:
        return [dict(row) for row in self.data_store.activities_by_city(city)]

    def _search_souvenirs(self, city: str) -> List[Dict[str, object]]:
        return [dict(row) for row in self.data_store.souvenirs_by_city(city)]

    def recommend(self, request: TravelRequest) -> TravelRecommendation:
        return self._run_recommendation(request)

    def recommend_with_memory(self, request: TravelRequest, memory_key: str) -> TravelRecommendation:
        return self._run_with_memory(request, memory_key)

    def recommend_with_controls(
        self,
        request: TravelRequest,
        max_agent_steps: int,
        max_tool_calls: int,
        allowed_tools: List[str],
    ) -> TravelRecommendation:
        self._validate_controls(max_agent_steps, max_tool_calls, allowed_tools)
        budget = ExecutionBudget(max_agent_steps=max_agent_steps, max_tool_calls=max_tool_calls)
        return self._run_recommendation(request, budget=budget)

    def recommend_with_controls_and_memory(
        self,
        request: TravelRequest,
        memory_key: str,
        max_agent_steps: int,
        max_tool_calls: int,
        allowed_tools: List[str],
    ) -> TravelRecommendation:
        self._validate_controls(max_agent_steps, max_tool_calls, allowed_tools)
        budget = ExecutionBudget(max_agent_steps=max_agent_steps, max_tool_calls=max_tool_calls)
        return self._run_with_memory(request, memory_key, budget, allowed_tools)

    def close(self) -> None:
        self.registry_center.close()
        self.event_bus.close()

    def read_memory(self, memory_key: str, limit: int = 50) -> List[str]:
        return self.memory_store.read_messages(memory_key, limit=limit)

    def query_memory(self, memory_key: str, query: str, limit: int = 10) -> List[str]:
        return self.memory_store.query_messages(memory_key, query, limit=limit)

    def _run_recommendation(self, request: TravelRequest, budget: Optional[ExecutionBudget] = None) -> TravelRecommendation:
        budget_token = set_current_budget(budget)
        try:
            self.event_bus.publish("recommend.requested", {
                "city": request.city,
                "days": request.days,
                "budget": request.budget,
                "travelers": request.travelers,
            })
            weights = self.skill_loader.load(request.preferences)
            try:
                route_message = self.a2a_router.send("manager-agent", "route-making-agent", "route_plan", {"city": request.city})
                trip_message = self.a2a_router.send("manager-agent", "trip-planner-agent", "trip_plan", {"days": request.days})
                _bounded_append(self.a2a_logs, route_message.__dict__, self.max_a2a_logs)
                _bounded_append(self.a2a_logs, trip_message.__dict__, self.max_a2a_logs)
                self.event_bus.publish("recommend.a2a_dispatched", {
                    "route_topic": route_message.topic,
                    "trip_topic": trip_message.topic,
                    "city": request.city,
                    "days": request.days,
                })
                self._process_a2a_replies()
            except Exception as error:
                self.event_bus.publish("recommend.a2a_dispatch_failed", {"city": request.city, "error": str(error)})
            engine_result = self.engine.run(request, weights, budget)
            result = engine_result.recommendation
            if budget is not None:
                self.event_bus.publish("recommend.budget_snapshot", budget.snapshot())
            self.event_bus.publish("recommend.completed", {
                "city": request.city,
                "hotel_count": len(result.hotel_options),
                "transport_count": len(result.transport_options),
                "itinerary_days": len(result.itinerary),
                "engagement_count": len(result.engagement_recommendations),
                "engine": engine_result.engine,
            })
            self.event_bus.publish("recommend.engine_selected", {
                "engine": engine_result.engine,
                "metadata": engine_result.metadata,
            })
            self._emit_shadow_engine_observation(request, weights, engine_result.engine)
            self.harness.capture(
                request=request,
                engine_name=engine_result.engine,
                engine_metadata=engine_result.metadata,
                a2a_logs=self.a2a_logs[-2:],
                mcp_logs=self.registry.audit_logs,
            )
            return result
        finally:
            reset_current_budget(budget_token)

    def _process_a2a_replies(self) -> None:
        """Drain agent inboxes (round trip) and pull replies into the manager log."""
        if not self.a2a_replies_enabled:
            return
        # Refresh in case tests/hosts swapped the router after construction.
        self.a2a_worker.router = self.a2a_router
        self.a2a_worker.drain("route-making-agent")
        self.a2a_worker.drain("trip-planner-agent")
        for reply in self.a2a_router.inbox("manager-agent"):
            if isinstance(reply, dict):
                record = dict(reply)
                record["direction"] = "reply"
                _bounded_append(self.a2a_logs, record, self.max_a2a_logs)

    def replay_last_harness_case(self) -> Dict[str, object]:
        return self.harness.replay_last(self)

    def _emit_shadow_engine_observation(
        self,
        request: TravelRequest,
        weights: Dict[str, float],
        selected_engine: str,
    ) -> None:
        mode = self.shadow_engine_mode
        if not mode:
            return
        if mode in {"", selected_engine, "native"}:
            return
        shadow_engine = build_engine_by_name(mode, self.manager)
        if shadow_engine.name == selected_engine:
            return
        try:
            shadow = shadow_engine.run(request, weights)
            payload = {
                "selected_engine": selected_engine,
                "shadow_engine": shadow.engine,
                "selected_adapter": selected_engine,
                "shadow_adapter": shadow.metadata.get("adapter", shadow.engine),
                "shadow_metadata": shadow.metadata,
                "shadow_engagement_count": len(shadow.recommendation.engagement_recommendations),
            }
            self.event_bus.publish("recommend.engine_shadow_compared", payload)
        except Exception as error:
            self.event_bus.publish(
                "recommend.engine_shadow_failed",
                {"selected_engine": selected_engine, "shadow_engine": mode, "error": str(error)},
            )

    def _validate_controls(self, max_agent_steps: int, max_tool_calls: int, allowed_tools: List[str]) -> None:
        if max_agent_steps < 2:
            raise ValueError("maxAgentSteps is too small")
        if max_tool_calls < 3:
            raise ValueError("maxToolCalls is too small")
        required_tools = {"search_hotels", "search_transports", "search_attractions"}
        if not required_tools.issubset(set(allowed_tools)):
            raise ValueError("allowedTools does not satisfy minimum required toolset")

    def _run_with_memory(
        self,
        request: TravelRequest,
        memory_key: str,
        budget: Optional[ExecutionBudget] = None,
        allowed_tools: Optional[List[str]] = None,
    ) -> TravelRecommendation:
        self.memory_store.append_message(memory_key, _serialize_event("request", request))
        result = self._run_recommendation(request, budget=budget)
        self.memory_store.append_message(memory_key, _serialize_event("recommendation", result))
        return result


def _serialize_event(event_type: str, payload: object) -> str:
    if isinstance(payload, TravelRequest):
        data = {
            "city": payload.city,
            "days": payload.days,
            "budget": payload.budget,
            "travelers": payload.travelers,
            "preferences": list(payload.preferences),
            "membership_tier": payload.membership_tier,
        }
    elif isinstance(payload, TravelRecommendation):
        data = {
            "hotels": [item.name for item in payload.hotel_options],
            "transports": [item.name for item in payload.transport_options],
            "itinerary": list(payload.itinerary),
            "engagement": list(payload.engagement_recommendations),
        }
    else:
        data = str(payload)
    return json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
