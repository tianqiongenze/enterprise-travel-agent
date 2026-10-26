"""Module defines API handlers."""

import logging
import os
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

fastapi_module = importlib.util.find_spec("fastapi")
FastAPI: Any = None
FastAPIRequest: Any = None
if fastapi_module is not None:
    fastapi_loaded = importlib.import_module("fastapi")
    FastAPI = getattr(fastapi_loaded, "FastAPI")
    FastAPIRequest = getattr(fastapi_loaded, "Request")
    HTTPException = getattr(fastapi_loaded, "HTTPException")

from ..access.control import enforce_tools_for_tier, evaluate_policy
from ..application.recommend_service import RecommendApplicationService
from ..membership_store import MembershipStore
from ..models import TravelRequest
from ..orchestrator import build_orchestrator
from ..traffic_guard import TrafficGuard
from .auth import AuthError, auth_mode, build_authenticator_from_env

logger = logging.getLogger("travel_agent.api")

project_root = str(Path(__file__).resolve().parents[5])
orchestrator = build_orchestrator(project_root)
shared_secret = os.getenv("TRAVEL_INTERNAL_SHARED_SECRET", "")
if not shared_secret:
    shared_secret = "demo-internal-secret"
    logger.warning(
        "TRAVEL_INTERNAL_SHARED_SECRET is not set - falling back to the public "
        "demo secret; this is acceptable for local dev only and is enforced by "
        "the go-live gate in staging/prod"
    )
trusted_client_id = os.getenv("TRAVEL_INTERNAL_CLIENT_ID", "techgroup-enterprise-travel-gateway")
# Dual-window secret acceptance for zero-downtime rotation: while the gateway
# has already switched to the new secret, the old one keeps verifying. Empty
# by default; set only during a rotation window.
shared_secret_previous = os.getenv("TRAVEL_INTERNAL_SHARED_SECRET_PREVIOUS", "")
# When true, /a2a/* endpoints require a valid internal HMAC signature even
# outside oidc mode: A2A traffic is service-to-service only.
a2a_internal_only = os.getenv("TRAVEL_A2A_INTERNAL_ONLY", "false").strip().lower() == "true"
membership_store = MembershipStore()
traffic_guard = TrafficGuard()
max_runtime_log_payload = int(os.getenv("TRAVEL_RUNTIME_RESPONSE_LOG_LIMIT", "50"))
oidc_authenticator = build_authenticator_from_env()
application_service = RecommendApplicationService(orchestrator)


def require_bearer_identity(authorization_header: str) -> Dict[str, str]:
    """Validate the caller in ``oidc`` auth mode and map claims to identity."""
    if auth_mode() != "oidc":
        return {}
    if oidc_authenticator is None:
        raise AuthError("TRAVEL_AUTH_MODE=oidc but TRAVEL_OIDC_ISSUER is not configured")
    return oidc_authenticator.identity_from_claims(
        oidc_authenticator.authenticate(authorization_header)
    )


def _verify_signature(idempotency_key: str, client_id: str, signature: str) -> bool:
    from ..security import verify_internal_signature

    if verify_internal_signature(idempotency_key, shared_secret, client_id, signature):
        return True
    if shared_secret_previous:
        return verify_internal_signature(idempotency_key, shared_secret_previous, client_id, signature)
    return False


def verify_a2a_internal_access(headers: Dict[str, Any]) -> None:
    """Gate /a2a/* when TRAVEL_A2A_INTERNAL_ONLY=true (401 on failure).

    Signature covers the receiver and sender so a captured header cannot be
    replayed against another inbox or sender.
    """
    if not a2a_internal_only:
        return
    client_id = str(headers.get("X-Internal-Client-Id", ""))
    signature = str(headers.get("X-Internal-Signature", ""))
    scope = str(headers.get("X-A2A-Scope", ""))
    if client_id != trusted_client_id:
        raise PermissionError("untrusted internal client")
    if not scope or not _verify_signature(scope, client_id, signature):
        raise PermissionError("invalid internal signature for a2a access")


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
    # In oidc mode the gateway forwards the end-user bearer token; service trust
    # (internal HMAC) stays mandatory on top of it.
    if auth_mode() == "oidc":
        identity = require_bearer_identity(runtime_headers.get("Authorization", ""))
        payload = {**payload, "_identity": identity}
    if not trace_id:
        raise ValueError("missing X-Trace-Id")
    if internal_client != trusted_client_id:
        raise ValueError("untrusted internal client")
    idempotency_key = str(payload.get("idempotencyKey", ""))
    if not idempotency_key or not _verify_signature(idempotency_key, internal_client, internal_sig):
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
        with trace_recommendation(trace_id, tenant_id, current_engine):
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
    try:
        application_service.plan_trip(request, result, tenant_id=tenant_id, user_id=user_id)
    except Exception as plan_error:  # noqa: BLE001 - read path survives domain invariant violations
        logger.warning("trip plan build skipped for city=%s: %s", request.city, plan_error)
    audit_logs = orchestrator.registry.audit_logs[-max_runtime_log_payload:]
    a2a_logs = orchestrator.a2a_logs[-max_runtime_log_payload:]
    return {
        "trace_id": trace_id,
        "memory_before": memory_before,
        "memory_after": memory_after,
        "memory_hits": memory_hits,
        "hotel_options": [item.__dict__ for item in result.hotel_options],
        "transport_options": [item.__dict__ for item in result.transport_options],
        "itinerary": result.itinerary,
        "engagement_recommendations": result.engagement_recommendations,
        "audit_logs": audit_logs,
        "a2a_logs": a2a_logs,
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
    from ..observability.tracing import configure_tracing, trace_recommendation

    configure_tracing()
    app = FastAPI(title="Enterprise Travel Agent API", version="0.1.0")

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/recommend")
    def recommend_endpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
        return recommend(payload)

    @app.post("/runtime/recommend")
    def runtime_recommend_endpoint(payload: Dict[str, Any], request: FastAPIRequest = None) -> Dict[str, Any]:
        runtime_headers = {
            "X-Trace-Id": request.headers.get("X-Trace-Id", ""),
            "X-Internal-Client-Id": request.headers.get("X-Internal-Client-Id", ""),
            "X-Internal-Signature": request.headers.get("X-Internal-Signature", ""),
            "Authorization": request.headers.get("Authorization", ""),
        }
        return runtime_recommend(payload, runtime_headers)

    @app.post("/a2a/send")
    def a2a_send_endpoint(payload: Dict[str, Any], request: FastAPIRequest = None) -> Dict[str, Any]:
        if request is not None:
            a2a_headers = {
                "X-Internal-Client-Id": request.headers.get("X-Internal-Client-Id", ""),
                "X-Internal-Signature": request.headers.get("X-Internal-Signature", ""),
                "X-A2A-Scope": request.headers.get("X-A2A-Scope", ""),
            }
            try:
                verify_a2a_internal_access(a2a_headers)
            except PermissionError as auth_error:
                raise HTTPException(status_code=401, detail=str(auth_error)) from auth_error
            if auth_mode() == "oidc":
                require_bearer_identity(request.headers.get("Authorization", ""))
        return a2a_send(payload)

    @app.get("/a2a/inbox/{receiver}")
    def a2a_inbox_endpoint(receiver: str, request: FastAPIRequest = None) -> Dict[str, Any]:
        if request is not None:
            a2a_headers = {
                "X-Internal-Client-Id": request.headers.get("X-Internal-Client-Id", ""),
                "X-Internal-Signature": request.headers.get("X-Internal-Signature", ""),
                "X-A2A-Scope": f"inbox.{receiver}",
            }
            try:
                verify_a2a_internal_access(a2a_headers)
            except PermissionError as auth_error:
                raise HTTPException(status_code=401, detail=str(auth_error)) from auth_error
            if auth_mode() == "oidc":
                require_bearer_identity(request.headers.get("Authorization", ""))
        return a2a_inbox(receiver)

    if os.getenv("TRAVEL_RUNTIME_GRPC_ENABLED", "false").strip().lower() == "true":
        from ..grpc.runtime_server import serve_grpc

        _grpc_server = serve_grpc(runtime_recommend)

        @app.get("/health/grpc")
        def grpc_health() -> Dict[str, str]:
            return {"status": "ok", "grpc_port": os.getenv("TRAVEL_RUNTIME_GRPC_PORT", "9092")}

    # GraphQL layer (fourth-round R1): mounted inside the app-build branch so
    # a missing optional dependency cannot break the REST surface.
    try:
        from ..graphql_schema import build_graphql_app as _build_graphql_app

        app.mount("/graphql", _build_graphql_app())

        @app.get("/graphql/health")
        def graphql_health() -> Dict[str, str]:
            return {"status": "graphql-schema-loaded"}
    except Exception as _graphql_error:  # pragma: no cover - optional dep
        print(f"[graphql] layer disabled: {_graphql_error}")
