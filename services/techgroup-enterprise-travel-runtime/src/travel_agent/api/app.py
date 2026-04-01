"""Module defines API handlers."""

import os
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib

fastapi_module = importlib.util.find_spec("fastapi")
FastAPI: Any = None
FastAPIRequest: Any = None
if fastapi_module is not None:
    fastapi_loaded = importlib.import_module("fastapi")
    FastAPI = getattr(fastapi_loaded, "FastAPI")
    FastAPIRequest = getattr(fastapi_loaded, "Request")

from ..access.control import enforce_tools_for_tier, evaluate_policy
from ..membership_store import MembershipStore
from ..models import TravelRequest
from ..orchestrator import build_orchestrator
from ..traffic_guard import TrafficGuard

project_root = str(Path(__file__).resolve().parents[5])
orchestrator = build_orchestrator(project_root)
shared_secret = os.getenv("TRAVEL_INTERNAL_SHARED_SECRET", "demo-internal-secret")
trusted_client_id = os.getenv("TRAVEL_INTERNAL_CLIENT_ID", "techgroup-enterprise-travel-gateway")
membership_store = MembershipStore()
traffic_guard = TrafficGuard()


def _verify_signature(idempotency_key: str, signature: str) -> bool:
    seed = idempotency_key + "." + shared_secret
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return signature.startswith(digest[:16]) or signature == digest


def recommend(payload: Dict[str, Any]) -> Dict[str, Any]:
    tier = str(payload.get("membershipTier", "basic")).strip().lower() or "basic"
    request = TravelRequest(
        city=payload.get("city", "北京"),
        days=int(payload.get("days", 3)),
        budget=float(payload.get("budget", 3000)),
        travelers=int(payload.get("travelers", 1)),
        preferences=list(payload.get("preferences", [])),
        membership_tier=tier,
    )
    result = orchestrator.recommend(request)
    return {
        "hotel_options": [item.__dict__ for item in result.hotel_options],
        "transport_options": [item.__dict__ for item in result.transport_options],
        "itinerary": result.itinerary,
        "engagement_recommendations": result.engagement_recommendations,
    }


def runtime_recommend(payload: Dict[str, Any], headers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    runtime_headers = headers or {}
    trace_id = runtime_headers.get("X-Trace-Id", "")
    internal_client = runtime_headers.get("X-Internal-Client-Id", "")
    internal_sig = runtime_headers.get("X-Internal-Signature", "")
    if not trace_id:
        raise ValueError("missing X-Trace-Id")
    if internal_client != trusted_client_id:
        raise ValueError("untrusted internal client")
    idempotency_key = str(payload.get("idempotencyKey", ""))
    if not idempotency_key or not _verify_signature(idempotency_key, internal_sig):
        raise ValueError("invalid internal signature")
    tenant_id = str(payload.get("tenantId", "")).strip()
    user_id = str(payload.get("userId", "")).strip()
    conversation_id = str(payload.get("conversationId", "")).strip()
    if not tenant_id or not user_id or not conversation_id:
        raise ValueError("missing conversation scope")

    client_ip = str(runtime_headers.get("X-Forwarded-For", "internal")).split(",")[0].strip() or "internal"
    if not traffic_guard.allow_request(f"{tenant_id}:{user_id}:{client_ip}"):
        raise ValueError("rate limit exceeded")
    if not traffic_guard.claim_idempotency(tenant_id, idempotency_key):
        raise ValueError("duplicate submission")
    if not traffic_guard.allow_circuit("runtime_recommend"):
        raise ValueError("service temporarily unavailable")
    inflight_scope = f"{tenant_id}:{str(payload.get('city', 'na')).strip() or 'na'}"
    if not traffic_guard.claim_inflight(inflight_scope):
        raise ValueError("service overloaded, please retry")

    memory_key = "%s:%s:%s" % (tenant_id, user_id, conversation_id)
    memory_before = orchestrator.read_memory(memory_key)
    tier_payload = str(payload.get("membershipTier", "")).strip().lower()
    tier = tier_payload or membership_store.get_tier(tenant_id, user_id) or "basic"
    membership_store.set_tier(tenant_id, user_id, tier)
    current_engine = getattr(orchestrator.engine, "name", "langgraph")
    requested_tools = list(payload.get("allowedTools", []))
    allowed_tools = enforce_tools_for_tier(tier, requested_tools)
    decision = evaluate_policy(
        tier=tier,
        engine=current_engine,
        allowed_tools=allowed_tools,
        max_agent_steps=int(payload.get("maxAgentSteps", 10)),
        max_tool_calls=int(payload.get("maxToolCalls", 10)),
    )
    if not decision.allow:
        raise ValueError(decision.reason)

    request = TravelRequest(
        city=payload.get("city", "北京"),
        days=int(payload.get("days", 3)),
        budget=float(payload.get("budget", 3000)),
        travelers=int(payload.get("travelers", 1)),
        preferences=list(payload.get("preferences", [])),
        membership_tier=tier,
    )
    try:
        result = orchestrator.recommend_with_controls_and_memory(
            request=request,
            memory_key=memory_key,
            max_agent_steps=int(payload.get("maxAgentSteps", 10)),
            max_tool_calls=int(payload.get("maxToolCalls", 10)),
            allowed_tools=allowed_tools,
        )
        traffic_guard.record_success("runtime_recommend")
    except Exception:
        traffic_guard.record_failure("runtime_recommend")
        raise
    finally:
        traffic_guard.release_inflight(inflight_scope)
    memory_after = orchestrator.read_memory(memory_key)
    memory_hits = orchestrator.query_memory(memory_key, request.city, limit=3)
    return {
        "trace_id": trace_id,
        "memory_before": memory_before,
        "memory_after": memory_after,
        "memory_hits": memory_hits,
        "hotel_options": [item.__dict__ for item in result.hotel_options],
        "transport_options": [item.__dict__ for item in result.transport_options],
        "itinerary": result.itinerary,
        "engagement_recommendations": result.engagement_recommendations,
        "audit_logs": orchestrator.registry.audit_logs,
        "a2a_logs": orchestrator.a2a_logs,
        "registered_agents": orchestrator.registry_center.list_services(),
        "registered_tools": orchestrator.registry_center.list_tools(),
    }


def a2a_send(payload: Dict[str, Any]) -> Dict[str, Any]:
    sender = str(payload.get("sender", "manager-agent"))
    receiver = str(payload.get("receiver", "route-making-agent"))
    topic = str(payload.get("topic", "custom"))
    message_payload = dict(payload.get("payload", {}))
    try:
        message = orchestrator.a2a_router.send(sender, receiver, topic, message_payload)
        return {"message": message.__dict__}
    except Exception as error:
        return {"message": None, "error": str(error)}


def a2a_inbox(receiver: str) -> Dict[str, Any]:
    try:
        messages = orchestrator.a2a_router.inbox(receiver)
        return {"receiver": receiver, "messages": messages}
    except Exception as error:
        return {"receiver": receiver, "messages": [], "error": str(error)}


if FastAPI is None:
    app = None
else:
    app = FastAPI(title="Enterprise Travel Agent API", version="0.1.0")

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/recommend")
    def recommend_endpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
        return recommend(payload)

    @app.post("/runtime/recommend")
    def runtime_recommend_endpoint(payload: Dict[str, Any], request: Any) -> Dict[str, Any]:
        runtime_headers = {
            "X-Trace-Id": request.headers.get("X-Trace-Id", ""),
            "X-Internal-Client-Id": request.headers.get("X-Internal-Client-Id", ""),
            "X-Internal-Signature": request.headers.get("X-Internal-Signature", ""),
        }
        return runtime_recommend(payload, runtime_headers)

    @app.post("/a2a/send")
    def a2a_send_endpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
        return a2a_send(payload)

    @app.get("/a2a/inbox/{receiver}")
    def a2a_inbox_endpoint(receiver: str) -> Dict[str, Any]:
        return a2a_inbox(receiver)
