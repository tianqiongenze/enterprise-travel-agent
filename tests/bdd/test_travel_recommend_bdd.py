"""BDD step definitions (fourth-round R9, pytest-bdd).

Scenario language: Gherkin (中文场景，见 tests/bdd/features/travel_recommend.feature).
"""

from __future__ import annotations

import importlib

import pytest

pytest_bdd = pytest.importorskip("pytest_bdd")

from pytest_bdd import given, parsers, scenario, then, when  # noqa: E402

FEATURE = str(__import__("pathlib").Path(__file__).parent / "features" / "travel_recommend.feature")


@pytest.fixture()
def ctx():
    return {}


@pytest.fixture()
def api_client(monkeypatch):
    monkeypatch.setenv("TRAVEL_EVENT_BUS", "local")
    monkeypatch.setenv("TRAVEL_EVENT_BUS_STRICT", "false")
    monkeypatch.setenv("TRAVEL_A2A_AUDIT_MIRROR_PULSAR", "false")
    monkeypatch.setenv("TRAVEL_A2A_TRANSPORT", "mock")
    monkeypatch.setenv("TRAVEL_MULTILEVEL_CACHE", "off")
    import src.travel_agent.api.app as app_module

    importlib.reload(app_module)
    from fastapi.testclient import TestClient

    return TestClient(app_module.app)


@scenario(FEATURE, "正常推荐返回完整行程骨架")
def test_normal_recommend():
    pass


@scenario(FEATURE, "空参数使用默认行程（三天北京）")
def test_default_recommend():
    pass


@scenario(FEATURE, "GraphQL 查询与 REST 契约一致")
def test_graphql_contract_alignment():
    pass


@scenario(FEATURE, "健康面与观测面始终可用")
def test_probes_always_up():
    pass


@scenario(FEATURE, "深度过高的 GraphQL 查询被拒绝")
def test_depth_guard():
    pass


@given("降级本地事件总线的运行时已就绪")
def runtime_ready(api_client, ctx):
    ctx["client"] = api_client
    assert api_client.get("/health").json()["status"] == "ok"


@when(parsers.parse('游客请求 "{city}" {days:d} 天推荐'))
def request_recommend(api_client, ctx, city, days):
    ctx["resp"] = api_client.post("/recommend", json={"city": city, "days": days})
    ctx["city"] = city


@when("游客请求默认参数推荐")
def request_default_recommend(api_client, ctx):
    ctx["resp"] = api_client.post("/recommend", json={})


@when(parsers.parse('游客通过 GraphQL 查询 "{city}" 的推荐'))
def request_graphql(api_client, ctx, city):
    ctx["gql"] = api_client.post(
        "/graphql",
        json={"query": f'query {{ recommend(payload: {{city: "{city}"}}) {{ city days hotels {{ name }} }} }}'},
    )


@when("运维探测 /health、/metrics 与 /graphql/health")
def probe_surfaces(api_client, ctx):
    ctx["probes"] = {
        "/health": api_client.get("/health"),
        "/metrics": api_client.get("/metrics"),
        "/graphql/health": api_client.get("/graphql/health"),
    }


@when("攻击者发送 10 层嵌套查询")
def send_deep_query(api_client, ctx):
    deep = "query { " * 10 + "health " + "} " * 10
    ctx["gql_deep"] = api_client.post("/graphql", json={"query": deep})


@then("响应包含 4 个核心区块")
def response_has_four_blocks(ctx):
    body = ctx["resp"].json()
    for key in ("hotel_options", "transport_options", "itinerary", "engagement_recommendations"):
        assert key in body, key


@then(parsers.parse('城市为 "{city}"'))
def city_matches(ctx, city):
    assert ctx["resp"].json()["city"] == city


@then(parsers.parse('GraphQL 返回城市 "{city}" 且包含酒店列表'))
def graphql_city(ctx, city):
    data = ctx["gql"].json()["data"]["recommend"]
    assert data["city"] == city
    assert isinstance(data["hotels"], list)


@then("三个探针全部 200")
def probes_ok(ctx):
    for path, resp in ctx["probes"].items():
        assert resp.status_code == 200, path


@then("GraphQL 返回 errors 且 data 为空")
def graphql_rejected(ctx):
    body = ctx["gql_deep"].json()
    assert body["data"] is None and body.get("errors")
