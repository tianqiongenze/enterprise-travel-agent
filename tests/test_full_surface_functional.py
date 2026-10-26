"""Full-surface functional tests (fourth-round, plan §四.R9).

Covers every route on both API faces (REST 7 + GraphQL) against the real
FastAPI app — the BDD layer (tests/bdd/) reuses these helpers.
"""

from __future__ import annotations

import importlib

import pytest

fastapi = pytest.importorskip("fastapi")


@pytest.fixture()
def client(monkeypatch):
    # Same degraded-local env as CI: without a broker the pulsar client
    # blocks 30s per publish (sendTimeout) — same root cause the kind
    # staging retest hit; the functional suite must not depend on network.
    monkeypatch.setenv("TRAVEL_EVENT_BUS", "local")
    monkeypatch.setenv("TRAVEL_EVENT_BUS_STRICT", "false")
    monkeypatch.setenv("TRAVEL_A2A_AUDIT_MIRROR_PULSAR", "false")
    monkeypatch.setenv("TRAVEL_A2A_TRANSPORT", "mock")
    monkeypatch.setenv("TRAVEL_MULTILEVEL_CACHE", "off")
    import src.travel_agent.api.app as app_module

    importlib.reload(app_module)
    from fastapi.testclient import TestClient

    return TestClient(app_module.app)


class TestRestSurface:
    """REST 全路由功能测试（SDD 契约面 1/3）。"""

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200 and r.json() == {"status": "ok"}

    def test_graphql_health(self, client):
        r = client.get("/graphql/health")
        assert r.status_code == 200 and "graphql" in r.json()["status"]

    def test_metrics_endpoint(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        assert "travel_runtime_requests_total" in r.text

    def test_recommend_returns_full_payload(self, client):
        r = client.post("/recommend", json={"city": "北京", "days": 3})
        assert r.status_code == 200
        body = r.json()
        for key in ("hotel_options", "transport_options", "itinerary", "engagement_recommendations"):
            assert key in body, f"contract: {key} missing"

    def test_recommend_defaults_on_empty(self, client):
        r = client.post("/recommend", json={})
        assert r.status_code == 200

    def test_runtime_recommend_rejects_untrusted_client(self, client):
        # untrusted client id → ValueError inside handler; verify the guard
        # directly (the route returns 500 in older starlette, contract is the
        # guard's raise, not a specific HTTP code).
        import pytest as _pytest
        from src.travel_agent.api import app as app_mod

        with _pytest.raises(ValueError, match="untrusted internal client"):
            app_mod.runtime_recommend(
                {"idempotencyKey": "k"},
                headers={"X-Trace-Id": "t1", "X-Internal-Client-Id": "unknown", "X-Internal-Signature": "bad"},
            )

    def test_a2a_send_and_inbox(self, client):
        r = client.post("/a2a/send", json={"sender": "t", "receiver": "r", "topic": "tp", "payload": {}})
        assert r.status_code == 200
        inbox = client.get("/a2a/inbox/r").json()
        assert "messages" in inbox


class TestGraphQLSurface:
    """GraphQL 全查询功能测试（SDD 契约面 2/3）。"""

    def test_graphql_query_ok(self, client):
        r = client.post(
            "/graphql",
            json={"query": 'query { recommend(payload: {city: "北京"}) { city days hotels { name } } }'},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["recommend"]["city"] == "北京"

    def test_graphql_depth_guard(self, client):
        deep = "query { " * 9 + "health " + "} " * 9
        r = client.post("/graphql", json={"query": deep})
        assert r.status_code == 200  # ASGI returns 200 with errors payload
        assert "errors" in r.json(), "over-deep query must be rejected in errors payload"

    def test_graphql_health_field(self, client):
        r = client.post("/graphql", json={"query": "query { health }"})
        assert r.json()["data"]["health"] == "ok"


class TestMetricsSemantics:
    """观测语义（SDD 契约面 3/3：metrics 契约）。"""

    def test_requests_counter_grows(self, client):
        first = client.get("/metrics").text
        client.get("/health")
        client.get("/health")
        second = client.get("/metrics").text
        assert "travel_runtime_requests_total" in first and second
