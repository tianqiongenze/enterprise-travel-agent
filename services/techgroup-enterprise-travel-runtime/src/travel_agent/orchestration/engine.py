"""Orchestration engines with real state-graph execution and step budgets.

The ``langgraph`` engine builds a genuine LangGraph ``StateGraph`` when the
package is installed (route -> trip -> engagement pipeline with shared state,
end finish); otherwise it falls back to the sequential adapter and the result
metadata records ``real_stategraph: "false"`` so deployments can distinguish
the two. Every stage consumes an agent step from the ambient
:class:`~travel_agent.orchestration.budget.ExecutionBudget` when one is active.
"""

from __future__ import annotations

from importlib.util import find_spec
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional

from ..agents.manager_agent import ManagerAgent
from ..models import TravelRecommendation, TravelRequest
from .budget import ExecutionBudget

logger = logging.getLogger("travel_agent.orchestration")


@dataclass
class EngineResult:
    recommendation: TravelRecommendation
    engine: str
    metadata: Dict[str, str]


class BaseOrchestrationEngine:
    name = "framework"

    def __init__(self, manager: ManagerAgent) -> None:
        self.manager = manager

    def run(
        self,
        request: TravelRequest,
        weights: Dict[str, float],
        budget: Optional[ExecutionBudget] = None,
    ) -> EngineResult:
        raise NotImplementedError("Framework engines must implement run()")


def _consume_step(budget: Optional[ExecutionBudget], step: str) -> None:
    if budget is not None:
        budget.consume_agent_step(step)


def _build_recommendation(manager: ManagerAgent, request: TravelRequest, weights: Dict[str, float]) -> TravelRecommendation:
    visa_agent = getattr(manager, "visa_agent", None)
    concierge_agent = getattr(manager, "concierge_agent", None)
    local_lifestyle_agent = getattr(manager, "local_lifestyle_agent", None)
    hotels, transports = manager.route_agent.plan_routes(request, weights)
    itinerary = manager.trip_agent.plan_trip(request, hotels, transports)
    engagement = (
        manager.food_agent.recommend_food(request)
        + manager.event_agent.recommend_events(request)
        + manager.loyalty_agent.build_growth_actions(request)
        + manager.weather_agent.build_risk_hints(request)
        + manager.ancillary_agent.build_upsell_actions(request)
        + (visa_agent.build_visa_guidance(request) if visa_agent is not None else [])
        + (concierge_agent.build_concierge_actions(request) if concierge_agent is not None else [])
        + (local_lifestyle_agent.recommend_local_lifestyle(request) if local_lifestyle_agent is not None else [])
    )
    return TravelRecommendation(
        hotel_options=hotels,
        transport_options=transports,
        itinerary=itinerary,
        engagement_recommendations=engagement,
    )


def _run_state_graph(manager: ManagerAgent, request: TravelRequest, weights: Dict[str, float]) -> TravelRecommendation:
    """Execute the pipeline as a real LangGraph StateGraph (requires langgraph)."""
    import importlib

    state_graph = getattr(importlib.import_module("langgraph.graph"), "StateGraph", None)
    if state_graph is None:
        raise ImportError("langgraph.graph.StateGraph unavailable")

    state: Dict[str, object] = {"request": request, "weights": weights}

    def node_route(state: Dict[str, object]) -> Dict[str, object]:
        hotels, transports = manager.route_agent.plan_routes(state["request"], state["weights"])
        return {"hotels": hotels, "transports": transports}

    def node_trip(state: Dict[str, object]) -> Dict[str, object]:
        itinerary = manager.trip_agent.plan_trip(
            state["request"], state["hotels"], state["transports"]
        )
        return {"itinerary": itinerary}

    def node_engagement(state: Dict[str, object]) -> Dict[str, object]:
        return {"engagement": _collect_engagement(manager, state["request"])}

    graph = state_graph(dict)
    graph.add_node("route", node_route)
    graph.add_node("trip", node_trip)
    graph.add_node("engagement", node_engagement)
    graph.set_entry_point("route")
    graph.add_edge("route", "trip")
    graph.add_edge("trip", "engagement")
    app = graph.compile()
    final = app.invoke(state)
    return TravelRecommendation(
        hotel_options=final.get("hotels", []),
        transport_options=final.get("transports", []),
        itinerary=final.get("itinerary", []),
        engagement_recommendations=final.get("engagement", []),
    )


def _collect_engagement(manager: ManagerAgent, request: TravelRequest) -> list:
    visa_agent = getattr(manager, "visa_agent", None)
    concierge_agent = getattr(manager, "concierge_agent", None)
    local_lifestyle_agent = getattr(manager, "local_lifestyle_agent", None)
    return (
        manager.food_agent.recommend_food(request)
        + manager.event_agent.recommend_events(request)
        + manager.loyalty_agent.build_growth_actions(request)
        + manager.weather_agent.build_risk_hints(request)
        + manager.ancillary_agent.build_upsell_actions(request)
        + (visa_agent.build_visa_guidance(request) if visa_agent is not None else [])
        + (concierge_agent.build_concierge_actions(request) if concierge_agent is not None else [])
        + (local_lifestyle_agent.recommend_local_lifestyle(request) if local_lifestyle_agent is not None else [])
    )


class LangGraphEngine(BaseOrchestrationEngine):
    name = "langgraph"

    def run(
        self,
        request: TravelRequest,
        weights: Dict[str, float],
        budget: Optional[ExecutionBudget] = None,
    ) -> EngineResult:
        _consume_step(budget, "route_plan")
        _consume_step(budget, "trip_plan")
        _consume_step(budget, "engagement_plan")
        real_stategraph = find_spec("langgraph") is not None
        if real_stategraph:
            try:
                rec = _run_state_graph(self.manager, request, weights)
            except Exception as error:
                logger.warning("langgraph StateGraph execution failed, falling back to sequential adapter: %s", error)
                real_stategraph = False
        if not real_stategraph:
            rec = _build_recommendation(self.manager, request, weights)
        return EngineResult(
            recommendation=rec,
            engine=self.name,
            metadata={
                "adapter": "langgraph",
                "available": str(find_spec("langgraph") is not None).lower(),
                "graph_nodes": "route,trip,engagement",
                "real_stategraph": str(real_stategraph).lower(),
            },
        )


class AgentScopeEngine(BaseOrchestrationEngine):
    name = "agentscope"

    def run(
        self,
        request: TravelRequest,
        weights: Dict[str, float],
        budget: Optional[ExecutionBudget] = None,
    ) -> EngineResult:
        _consume_step(budget, "route_plan")
        _consume_step(budget, "trip_plan")
        _consume_step(budget, "engagement_plan")
        rec = _build_recommendation(self.manager, request, weights)
        return EngineResult(
            recommendation=rec,
            engine=self.name,
            metadata={
                "adapter": "agentscope-ai",
                "available": str(find_spec("agentscope") is not None).lower(),
                "session_mode": "multi-role",
                "real_stategraph": "false",
            },
        )


class OneAgentsEngine(BaseOrchestrationEngine):
    name = "oneagents"

    def run(
        self,
        request: TravelRequest,
        weights: Dict[str, float],
        budget: Optional[ExecutionBudget] = None,
    ) -> EngineResult:
        _consume_step(budget, "route_plan")
        _consume_step(budget, "trip_plan")
        _consume_step(budget, "engagement_plan")
        rec = _build_recommendation(self.manager, request, weights)
        return EngineResult(
            recommendation=rec,
            engine=self.name,
            metadata={
                "adapter": "oneagents",
                "available": str(find_spec("oneagents") is not None).lower(),
                "contract_mode": "task-contract",
                "real_stategraph": "false",
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
