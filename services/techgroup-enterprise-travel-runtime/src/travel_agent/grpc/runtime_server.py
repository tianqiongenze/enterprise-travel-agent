"""RuntimeService gRPC server: lands the v1 contract on the Python runtime.

The contract in ``data-contracts/grpc/v1/runtime.proto`` is now served, not
just generated: this server reuses the same application function
(:func:`travel_agent.api.app.runtime_recommend`) as the HTTP path, so HTTP and
gRPC share validation, budgets and policy. Enable with
``TRAVEL_RUNTIME_GRPC_ENABLED=true`` (port ``TRAVEL_RUNTIME_GRPC_PORT``, 9092).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import grpc

from .generated.v1 import common_pb2, runtime_pb2, runtime_pb2_grpc

logger = logging.getLogger("travel_agent.grpc.runtime")


def _structs(rows: List[Dict[str, Any]]):
    from google.protobuf import struct_pb2

    out = []
    for row in rows:
        item = struct_pb2.Struct()
        item.update(row if isinstance(row, dict) else {"value": str(row)})
        out.append(item)
    return out


def _item(item: Dict[str, Any]) -> common_pb2.RecommendationItem:
    entry = common_pb2.RecommendationItem(
        id=str(item.get("id", "")),
        name=str(item.get("name", "")),
        score=float(item.get("score", 0.0) or 0.0),
        price=float(item.get("price", 0.0) or 0.0),
        reason=str(item.get("reason", "")),
    )
    tags = item.get("tags") or []
    if isinstance(tags, list):
        entry.tags.extend([str(tag) for tag in tags])
    return entry


class RuntimeServicer(runtime_pb2_grpc.RuntimeServiceServicer):
    """Serves Recommend by delegating to the HTTP application function."""

    def __init__(self, runtime_recommend) -> None:
        # runtime_recommend(payload, headers) from travel_agent.api.app
        self._runtime_recommend = runtime_recommend

    def Recommend(self, request: runtime_pb2.RuntimeRecommendRequest, context):  # noqa: N802
        payload: Dict[str, Any] = {
            "tenantId": request.context.tenant_id,
            "userId": request.context.user_id,
            "conversationId": request.context.conversation_id,
            "idempotencyKey": request.context.idempotency_key,
            "policyId": request.policy_id,
            "city": request.city,
            "days": request.days,
            "budget": request.budget,
            "travelers": request.travelers,
            "membershipTier": request.membership_tier,
            "preferences": list(request.preferences),
            "maxAgentSteps": request.max_agent_steps,
            "maxToolCalls": request.max_tool_calls,
            "allowedTools": list(request.allowed_tools),
        }
        headers = {
            "X-Trace-Id": request.context.trace_id,
            "X-Internal-Client-Id": request.context.internal_client_id,
            "X-Internal-Signature": request.context.internal_signature,
        }
        try:
            result = self._runtime_recommend(payload, headers)
        except ValueError as error:
            context.abort(  # type: ignore[union-attr]
                code=grpc.StatusCode.INVALID_ARGUMENT,
                details=str(error),
            )
            return runtime_pb2.RuntimeRecommendResponse()

        response = runtime_pb2.RuntimeRecommendResponse(
            trace_id=result.get("trace_id", ""),
            registered_agents=list(result.get("registered_agents", [])),
            registered_tools=list(result.get("registered_tools", [])),
        )
        response.hotel_options.extend([_item(row) for row in result.get("hotel_options", [])])
        response.transport_options.extend([_item(row) for row in result.get("transport_options", [])])
        response.itinerary.extend(_structs(result.get("itinerary", [])))
        response.engagement_recommendations.extend(_structs(result.get("engagement_recommendations", [])))
        response.memory_before.extend(_structs(result.get("memory_before", [])))
        response.memory_after.extend(_structs(result.get("memory_after", [])))
        response.memory_hits.extend(_structs(result.get("memory_hits", [])))
        response.audit_logs.extend(_structs(result.get("audit_logs", [])))
        response.a2a_logs.extend(_structs(result.get("a2a_logs", [])))
        return response


def serve_grpc(runtime_recommend) -> Any:
    """Start the RuntimeService gRPC server in a background thread."""
    import grpc
    from concurrent import futures

    port = int(os.getenv("TRAVEL_RUNTIME_GRPC_PORT", "9092"))
    max_workers = int(os.getenv("TRAVEL_RUNTIME_GRPC_MAX_WORKERS", "16"))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    runtime_pb2_grpc.add_RuntimeServiceServicer_to_server(RuntimeServicer(runtime_recommend), server)
    bound = server.add_insecure_port(f"[::]:{port}")
    if bound == 0:
        raise RuntimeError(f"gRPC server failed to bind port {port}")
    server.start()
    logger.info("runtime gRPC server listening on port %s", port)
    return server
