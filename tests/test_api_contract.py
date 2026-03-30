"""Module provides service components and helpers."""

import unittest
from unittest.mock import patch

from src.travel_agent.api import app as api_module
from src.travel_agent.api.app import runtime_recommend, a2a_send, a2a_inbox
from src.travel_agent.a2a.router import A2ARouter, MockDistributedA2ATransport
from src.travel_agent.orchestration.engine import build_engine_by_name
from src.travel_agent.security import make_internal_signature


class ApiContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        api_module.orchestrator.a2a_router = A2ARouter(transport=MockDistributedA2ATransport())

    def test_fastapi_optional_import_contract(self) -> None:
        self.assertTrue(hasattr(api_module, "app"))

    def test_runtime_recommend_rejects_missing_trace(self) -> None:
        with self.assertRaises(ValueError):
            runtime_recommend(
                payload={"idempotencyKey": "abc", "allowedTools": ["search_hotels", "search_transports", "search_attractions"]},
                headers={"X-Internal-Client-Id": "techgroup-enterprise-travel-gateway", "X-Internal-Signature": "sig"},
            )

    def test_runtime_recommend_accepts_valid_internal_headers(self) -> None:
        idem = "idem-1"
        sig = make_internal_signature(idem, "demo-internal-secret")
        result = runtime_recommend(
            payload={
                "tenantId": "tenant-1",
                "userId": "user-1",
                "conversationId": "conv-1",
                "idempotencyKey": idem,
                "city": "北京",
                "days": 2,
                "budget": 3000,
                "travelers": 1,
                "preferences": ["family"],
                "maxAgentSteps": 10,
                "maxToolCalls": 10,
                "allowedTools": ["search_hotels", "search_transports", "search_attractions"],
            },
            headers={
                "X-Trace-Id": "trace-1",
                "X-Internal-Client-Id": "techgroup-enterprise-travel-gateway",
                "X-Internal-Signature": sig,
            },
        )
        self.assertIn("trace_id", result)

    def test_runtime_recommend_requires_conversation_scope(self) -> None:
        idem = "idem-scope"
        sig = make_internal_signature(idem, "demo-internal-secret")
        with self.assertRaises(ValueError):
            runtime_recommend(
                payload={
                    "idempotencyKey": idem,
                    "city": "北京",
                    "days": 2,
                    "budget": 3000,
                    "travelers": 1,
                    "preferences": ["family"],
                    "maxAgentSteps": 10,
                    "maxToolCalls": 10,
                    "allowedTools": ["search_hotels", "search_transports", "search_attractions"],
                },
                headers={
                    "X-Trace-Id": "trace-scope",
                    "X-Internal-Client-Id": "techgroup-enterprise-travel-gateway",
                    "X-Internal-Signature": sig,
                },
            )

    def test_runtime_recommend_returns_memory_snapshots(self) -> None:
        import os

        previous = os.environ.get("TRAVEL_MEMORY_BACKEND")
        os.environ["TRAVEL_MEMORY_BACKEND"] = "vector"
        idem = "idem-memory-1"
        sig = make_internal_signature(idem, "demo-internal-secret")
        result = runtime_recommend(
            payload={
                "tenantId": "tenant-1",
                "userId": "user-1",
                "conversationId": "conv-memory",
                "idempotencyKey": idem,
                "city": "北京",
                "days": 2,
                "budget": 3000,
                "travelers": 1,
                "preferences": ["family"],
                "maxAgentSteps": 10,
                "maxToolCalls": 10,
                "allowedTools": ["search_hotels", "search_transports", "search_attractions"],
            },
            headers={
                "X-Trace-Id": "trace-memory",
                "X-Internal-Client-Id": "techgroup-enterprise-travel-gateway",
                "X-Internal-Signature": sig,
            },
        )
        self.assertEqual(result.get("memory_before"), [])
        self.assertTrue(len(result.get("memory_after", [])) >= 2)

        idem_2 = "idem-memory-2"
        sig_2 = make_internal_signature(idem_2, "demo-internal-secret")
        result_2 = runtime_recommend(
            payload={
                "tenantId": "tenant-1",
                "userId": "user-1",
                "conversationId": "conv-memory",
                "idempotencyKey": idem_2,
                "city": "北京",
                "days": 2,
                "budget": 3000,
                "travelers": 1,
                "preferences": ["family"],
                "maxAgentSteps": 10,
                "maxToolCalls": 10,
                "allowedTools": ["search_hotels", "search_transports", "search_attractions"],
            },
            headers={
                "X-Trace-Id": "trace-memory",
                "X-Internal-Client-Id": "techgroup-enterprise-travel-gateway",
                "X-Internal-Signature": sig_2,
            },
        )
        self.assertTrue(len(result_2.get("memory_before", [])) >= 2)
        self.assertTrue(len(result_2.get("memory_after", [])) >= 4)
        self.assertTrue(len(result_2.get("memory_hits", [])) >= 1)
        if previous is None:
            del os.environ["TRAVEL_MEMORY_BACKEND"]
        else:
            os.environ["TRAVEL_MEMORY_BACKEND"] = previous

    def test_a2a_send_and_inbox(self) -> None:
        send_result = a2a_send(
            {
                "sender": "manager-agent",
                "receiver": "trip-planner-agent",
                "topic": "test-topic",
                "payload": {"hello": "world"},
            }
        )
        self.assertIn("message", send_result)
        inbox = a2a_inbox("trip-planner-agent")
        self.assertTrue(len(inbox["messages"]) >= 1)

    def test_runtime_recommend_rejects_engine_not_allowed_for_tier(self) -> None:
        previous_engine = api_module.orchestrator.engine
        api_module.orchestrator.engine = build_engine_by_name("oneagents", api_module.orchestrator.manager)
        idem = "idem-tier-1"
        sig = make_internal_signature(idem, "demo-internal-secret")
        with self.assertRaises(ValueError):
            runtime_recommend(
                payload={
                    "tenantId": "tenant-1",
                    "userId": "user-1",
                    "conversationId": "conv-tier",
                    "membershipTier": "basic",
                    "idempotencyKey": idem,
                    "city": "北京",
                    "days": 2,
                    "budget": 3000,
                    "travelers": 1,
                    "preferences": ["family"],
                    "maxAgentSteps": 10,
                    "maxToolCalls": 10,
                    "allowedTools": ["search_hotels", "search_transports", "search_attractions"],
                },
                headers={
                    "X-Trace-Id": "trace-tier",
                    "X-Internal-Client-Id": "techgroup-enterprise-travel-gateway",
                    "X-Internal-Signature": sig,
                },
            )
        api_module.orchestrator.engine = previous_engine

    def test_runtime_recommend_rejects_duplicate_submission(self) -> None:
        idem = "idem-dup-1"
        sig = make_internal_signature(idem, "demo-internal-secret")
        with patch("src.travel_agent.api.app.traffic_guard.claim_idempotency", return_value=False):
            with self.assertRaises(ValueError):
                runtime_recommend(
                    payload={
                        "tenantId": "tenant-1",
                        "userId": "user-1",
                        "conversationId": "conv-dup",
                        "membershipTier": "basic",
                        "idempotencyKey": idem,
                        "city": "北京",
                        "days": 2,
                        "budget": 3000,
                        "travelers": 1,
                        "preferences": ["family"],
                        "maxAgentSteps": 10,
                        "maxToolCalls": 10,
                        "allowedTools": ["search_hotels", "search_transports", "search_attractions"],
                    },
                    headers={
                        "X-Trace-Id": "trace-dup",
                        "X-Internal-Client-Id": "techgroup-enterprise-travel-gateway",
                        "X-Internal-Signature": sig,
                    },
                )


if __name__ == "__main__":
    unittest.main()
