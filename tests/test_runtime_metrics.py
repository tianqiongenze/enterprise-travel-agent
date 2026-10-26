"""TDD tests for /metrics and async queue peak-shaving (R8+R5)."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")


@pytest.mark.asyncio
async def test_metrics_endpoint_counts_requests(monkeypatch):
    import importlib

    import src.travel_agent.api.app as app_module
    importlib.reload(app_module)
    from fastapi.testclient import TestClient

    client = TestClient(app_module.app)
    client.get("/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert 'route="/health"' in body and "travel_runtime_requests_total" in body
    assert "travel_runtime_request_latency_seconds_count" in body


@pytest.mark.asyncio
async def test_metrics_includes_cache_counters(monkeypatch):
    import importlib

    import src.travel_agent.api.app as app_module
    importlib.reload(app_module)
    from fastapi.testclient import TestClient

    client = TestClient(app_module.app)
    body = client.get("/metrics").text
    assert "travel_cache_hit_rate" in body


@pytest.mark.asyncio
async def test_metrics_survives_redis_outage(monkeypatch):
    # /metrics must render even when the cache raises (fail-open)
    import importlib

    import src.travel_agent.api.app as app_module
    importlib.reload(app_module)
    from fastapi.testclient import TestClient

    def boom():
        raise RuntimeError("cache down")

    monkeypatch.setattr(app_module.orchestrator.multilevel_cache, "prometheus_metrics", boom)
    client = TestClient(app_module.app)
    assert client.get("/metrics").status_code == 200


def test_reject_counter_wired(monkeypatch):
    from src.travel_agent.observability.metrics import runtime_metrics

    runtime_metrics.observe_reject("token_bucket_test")
    body = runtime_metrics.render().decode()
    assert 'reason="token_bucket_test"' in body
