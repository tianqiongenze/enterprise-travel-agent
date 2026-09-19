"""Module provides service components and helpers."""

from importlib.util import find_spec
import os
from dataclasses import dataclass
from typing import Dict

from ..agents.manager_agent import ManagerAgent
from ..models import TravelRecommendation, TravelRequest


@dataclass
class EngineResult:
    recommendation: TravelRecommendation
    engine: str
    metadata: Dict[str, str]


class BaseOrchestrationEngine:
    name = "framework"

    def __init__(self, manager: ManagerAgent) -> None:
        self.manager = manager

    def run(self, request: TravelRequest, weights: Dict[str, float]) -> EngineResult:
        raise NotImplementedError("Framework engines must implement run()")


class LangGraphEngine(BaseOrchestrationEngine):
    name = "langgraph"

    def run(self, request: TravelRequest, weights: Dict[str, float]) -> EngineResult:
        visa_agent = getattr(self.manager, "visa_agent", None)
        concierge_agent = getattr(self.manager, "concierge_agent", None)
        local_lifestyle_agent = getattr(self.manager, "local_lifestyle_agent", None)
        hotels, transports = self.manager.route_agent.plan_routes(request, weights)
        itinerary = self.manager.trip_agent.plan_trip(request, hotels, transports)
        engagement = (
            self.manager.food_agent.recommend_food(request)
            + self.manager.event_agent.recommend_events(request)
            + self.manager.loyalty_agent.build_growth_actions(request)
            + self.manager.weather_agent.build_risk_hints(request)
            + self.manager.ancillary_agent.build_upsell_actions(request)
            + (visa_agent.build_visa_guidance(request) if visa_agent is not None else [])
            + (concierge_agent.build_concierge_actions(request) if concierge_agent is not None else [])
            + (local_lifestyle_agent.recommend_local_lifestyle(request) if local_lifestyle_agent is not None else [])
        )
        rec = TravelRecommendation(
            hotel_options=hotels,
            transport_options=transports,
            itinerary=itinerary,
            engagement_recommendations=engagement,
        )
        return EngineResult(
            recommendation=rec,
            engine=self.name,
            metadata={
                "adapter": "langgraph",
                "available": str(find_spec("langgraph") is not None).lower(),
                "graph_nodes": "route,trip,engagement,risk,compliance",
                "note": "state-graph-bound",
            },
        )


class AgentScopeEngine(BaseOrchestrationEngine):
    name = "agentscope"

    def run(self, request: TravelRequest, weights: Dict[str, float]) -> EngineResult:
        visa_agent = getattr(self.manager, "visa_agent", None)
        concierge_agent = getattr(self.manager, "concierge_agent", None)
        local_lifestyle_agent = getattr(self.manager, "local_lifestyle_agent", None)
        hotels, transports = self.manager.route_agent.plan_routes(request, weights)
        itinerary = self.manager.trip_agent.plan_trip(request, hotels, transports)
        # AgentScope-like multi-role collaboration output.
        engagement = (
            self.manager.food_agent.recommend_food(request)
            + self.manager.event_agent.recommend_events(request)
            + self.manager.weather_agent.build_risk_hints(request)
            + (visa_agent.build_visa_guidance(request) if visa_agent is not None else [])
            + (concierge_agent.build_concierge_actions(request) if concierge_agent is not None else [])
            + self.manager.loyalty_agent.build_growth_actions(request)
            + (local_lifestyle_agent.recommend_local_lifestyle(request) if local_lifestyle_agent is not None else [])
        )
        rec = TravelRecommendation(
            hotel_options=hotels,
            transport_options=transports,
            itinerary=itinerary,
            engagement_recommendations=engagement,
        )
        return EngineResult(
            recommendation=rec,
            engine=self.name,
            metadata={
                "adapter": "agentscope-ai",
                "available": str(find_spec("agentscope") is not None).lower(),
                "session_mode": "multi-role",
                "note": "agentscope-session-bound",
            },
        )


class OneAgentsEngine(BaseOrchestrationEngine):
    name = "oneagents"

    def run(self, request: TravelRequest, weights: Dict[str, float]) -> EngineResult:
        concierge_agent = getattr(self.manager, "concierge_agent", None)
        local_lifestyle_agent = getattr(self.manager, "local_lifestyle_agent", None)
        hotels, transports = self.manager.route_agent.plan_routes(request, weights)
        itinerary = self.manager.trip_agent.plan_trip(request, hotels, transports)
        engagement = (
            self.manager.food_agent.recommend_food(request)
            + self.manager.event_agent.recommend_events(request)
            + self.manager.ancillary_agent.build_upsell_actions(request)
            + (concierge_agent.build_concierge_actions(request) if concierge_agent is not None else [])
            + (local_lifestyle_agent.recommend_local_lifestyle(request) if local_lifestyle_agent is not None else [])
        )
        rec = TravelRecommendation(
            hotel_options=hotels,
            transport_options=transports,
            itinerary=itinerary,
            engagement_recommendations=engagement,
        )
        return EngineResult(
            recommendation=rec,
            engine=self.name,
            metadata={
                "adapter": "oneagents",
                "available": str(find_spec("oneagents") is not None).lower(),
                "contract_mode": "task-contract",
                "note": "oneagents-contract-bound",
            },
        )


def build_engine_by_name(mode: str, manager: ManagerAgent) -> BaseOrchestrationEngine:
    normalized = (mode or "").strip().lower()
    strict = os.getenv("TRAVEL_ORCHESTRATION_STRICT", "false").strip().lower() == "true"
    fallback = os.getenv("TRAVEL_ORCHESTRATION_FALLBACK_ENGINE", "langgraph").strip().lower()

    resolved = _resolve_engine_name(normalized)
    if resolved is not None:
        return _build_resolved_engine(resolved, manager)

    # local/native/unknown modes are redirected to configured framework fallback.
    fallback_resolved = _resolve_engine_name(fallback)
    if fallback_resolved is None:
        fallback_resolved = "langgraph"

    if strict and normalized not in {"", "local", "native"}:
        raise RuntimeError("Unsupported orchestration engine: %s" % normalized)

    return _build_resolved_engine(fallback_resolved, manager)


def build_engine_from_env(manager: ManagerAgent) -> BaseOrchestrationEngine:
    mode = os.getenv("TRAVEL_ORCHESTRATION_ENGINE", "langgraph")
    return build_engine_by_name(mode, manager)


def _resolve_engine_name(mode: str) -> str | None:
    normalized = (mode or "").strip().lower()
    if normalized == "langgraph":
        return "langgraph"
    if normalized in {"agentscope", "agentscope-ai"}:
        return "agentscope"
    if normalized in {"oneagents", "oneagent"}:
        return "oneagents"
    return None


def _build_resolved_engine(resolved: str, manager: ManagerAgent) -> BaseOrchestrationEngine:
    if resolved == "langgraph":
        return LangGraphEngine(manager)
    if resolved == "agentscope":
        return AgentScopeEngine(manager)
    return OneAgentsEngine(manager)


