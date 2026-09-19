"""RuntimeService gRPC contract tests (in-process server on an ephemeral port)."""

from __future__ import annotations

import unittest

import grpc

from src.travel_agent.api.app import runtime_recommend
from src.travel_agent.grpc.generated.v1 import common_pb2, runtime_pb2, runtime_pb2_grpc
from src.travel_agent.grpc.runtime_server import RuntimeServicer
from src.travel_agent.security import make_internal_signature

_CLIENT_ID = "techgroup-enterprise-travel-gateway"


def _context_headers() -> runtime_pb2.RuntimeRecommendRequest.ContextHeaders:
    idem = "grpc-idem-1"
    return common_pb2.ContextHeaders(
        trace_id="trace-grpc-1",
        internal_client_id=_CLIENT_ID,
        internal_signature=make_internal_signature(idem, "demo-internal-secret", _CLIENT_ID),
        tenant_id="tenant-1",
        user_id="user-1",
        conversation_id="conv-grpc",
        idempotency_key=idem,
    )


class RuntimeGrpcContractTestCase(unittest.TestCase):
    def test_recommend_roundtrip_over_grpc(self) -> None:
        server = grpc.server(__import__("concurrent").futures.ThreadPoolExecutor(max_workers=4))
        runtime_pb2_grpc.add_RuntimeServiceServicer_to_server(RuntimeServicer(runtime_recommend), server)
        port = server.add_insecure_port("127.0.0.1:0")
        server.start()
        try:
            channel = grpc.insecure_channel(f"127.0.0.1:{port}")
            stub = runtime_pb2_grpc.RuntimeServiceStub(channel)
            request = runtime_pb2.RuntimeRecommendRequest(
                context=_context_headers(),
                city="北京",
                days=2,
                budget=3000.0,
                travelers=1,
                membership_tier="basic",
                preferences=["budget"],
                max_agent_steps=10,
                max_tool_calls=10,
                allowed_tools=["search_hotels", "search_transports", "search_attractions"],
            )
            response = stub.Recommend(request, timeout=15)
            self.assertEqual(response.trace_id, "trace-grpc-1")
            self.assertGreaterEqual(len(response.hotel_options), 1)
            self.assertIsInstance(response.hotel_options[0], common_pb2.RecommendationItem)
            self.assertIn("search_hotels", response.registered_tools)
        finally:
            server.stop(grace=None)

    def test_contract_violation_maps_to_invalid_argument(self) -> None:
        server = grpc.server(__import__("concurrent").futures.ThreadPoolExecutor(max_workers=4))
        runtime_pb2_grpc.add_RuntimeServiceServicer_to_server(RuntimeServicer(runtime_recommend), server)
        port = server.add_insecure_port("127.0.0.1:0")
        server.start()
        try:
            channel = grpc.insecure_channel(f"127.0.0.1:{port}")
            stub = runtime_pb2_grpc.RuntimeServiceStub(channel)
            headers = _context_headers()
            headers.internal_signature = "bad-signature"
            request = runtime_pb2.RuntimeRecommendRequest(
                context=headers,
                city="北京",
                days=2,
                budget=3000.0,
                travelers=1,
                max_agent_steps=10,
                max_tool_calls=10,
                allowed_tools=["search_hotels", "search_transports", "search_attractions"],
            )
            with self.assertRaises(grpc.RpcError) as raised:
                stub.Recommend(request, timeout=15)
            self.assertEqual(raised.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)
        finally:
            server.stop(grace=None)


if __name__ == "__main__":
    unittest.main()
