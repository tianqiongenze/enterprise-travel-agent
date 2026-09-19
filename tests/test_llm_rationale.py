"""Unit tests for the optional LLM rationale layer (agents/llm.py)."""

import os

import pytest

from src.travel_agent.agents.llm import (
    DashScopeLlmProvider,
    LlmRationaleDecorator,
    NullLlmProvider,
    create_rationale_provider,
)


@pytest.fixture(autouse=True)
def _restore_llm_env(monkeypatch):
    keys = [
        "TRAVEL_LLM_BACKEND",
        "TRAVEL_LLM_API_KEY",
        "TRAVEL_LLM_BASE_URL",
        "TRAVEL_LLM_MODEL",
        "TRAVEL_LLM_TIMEOUT_SEC",
        "AI_DASHSCOPE_API_KEY",
        "DASHSCOPE_API_KEY",
    ]
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _sample_items():
    return [
        {"type": "food", "title": "杭帮菜老字号", "reason": "本地口碑"},
        {"type": "event", "title": "西湖夜游", "reason": "时段匹配"},
    ]


class TestCreateRationaleProvider:
    def test_auto_without_key_returns_null(self):
        provider = create_rationale_provider()
        assert isinstance(provider, NullLlmProvider)
        assert provider.provider_name == "null"

    def test_off_forces_null_even_with_key(self, monkeypatch):
        monkeypatch.setenv("AI_DASHSCOPE_API_KEY", "sk-test")
        monkeypatch.setenv("TRAVEL_LLM_BACKEND", "off")
        assert isinstance(create_rationale_provider(), NullLlmProvider)

    def test_auto_with_key_returns_dashscope(self, monkeypatch):
        monkeypatch.setenv("AI_DASHSCOPE_API_KEY", "sk-test")
        provider = create_rationale_provider()
        assert isinstance(provider, DashScopeLlmProvider)

    def test_dashscope_without_key_falls_back_to_null(self, monkeypatch, caplog):
        monkeypatch.setenv("TRAVEL_LLM_BACKEND", "dashscope")
        with caplog.at_level("WARNING", logger="travel_agent.agents.llm"):
            provider = create_rationale_provider()
        assert isinstance(provider, NullLlmProvider)
        assert any("no API key" in r.message for r in caplog.records)

    def test_dashscope_with_key_enabled(self, monkeypatch):
        monkeypatch.setenv("TRAVEL_LLM_BACKEND", "dashscope")
        monkeypatch.setenv("TRAVEL_LLM_API_KEY", "sk-test")
        assert isinstance(create_rationale_provider(), DashScopeLlmProvider)


class TestDashScopeLlmProvider:
    def test_parse_lines(self, monkeypatch):
        monkeypatch.setenv("TRAVEL_LLM_API_KEY", "sk-test")
        provider = DashScopeLlmProvider()

        class FakeResponse:
            status_code = 200
            text = ""

            def json(self):
                return {
                    "choices": [
                        {"message": {"content": "理由一\n- 理由二\n• 理由三"}}
                    ]
                }

        def fake_post(url, headers=None, json=None, timeout=None):
            assert "/chat/completions" in url
            assert headers["Authorization"] == "Bearer sk-test"
            assert json["model"] == "qwen-plus"
            return FakeResponse()

        monkeypatch.setattr("requests.post", fake_post)
        reasons = provider.refine_reasons({"city": "杭州"}, _sample_items() + [{"title": "x", "reason": "y"}])
        assert reasons[:2] == ["理由一", "理由二"]

    def test_http_error_raises(self, monkeypatch):
        monkeypatch.setenv("TRAVEL_LLM_API_KEY", "sk-test")
        provider = DashScopeLlmProvider()

        class FakeResponse:
            status_code = 401
            text = "unauthorized"

            def json(self):
                return {}

        monkeypatch.setattr("requests.post", lambda *a, **kw: FakeResponse())
        with pytest.raises(RuntimeError, match="llm chat failed"):
            provider.refine_reasons({"city": "杭州"}, _sample_items())

    def test_too_few_lines_raises(self, monkeypatch):
        monkeypatch.setenv("TRAVEL_LLM_API_KEY", "sk-test")
        provider = DashScopeLlmProvider()

        class FakeResponse:
            status_code = 200
            text = ""

            def json(self):
                return {"choices": [{"message": {"content": "只有一条"}}]}

        monkeypatch.setattr("requests.post", lambda *a, **kw: FakeResponse())
        with pytest.raises(RuntimeError, match="llm returned 1 reasons"):
            provider.refine_reasons({"city": "杭州"}, _sample_items())


class TestLlmRationaleDecorator:
    def test_enrich_sets_reason_source(self):
        class FixedProvider:
            provider_name = "test:fixed"

            def refine_reasons(self, request_context, items):
                return ["LLM理由一", "LLM理由二"]

        enriched = LlmRationaleDecorator(FixedProvider()).enrich({}, _sample_items())
        assert [row["reason"] for row in enriched] == ["LLM理由一", "LLM理由二"]
        assert all(row["reasonSource"] == "test:fixed" for row in enriched)

    def test_degradation_on_provider_error(self, caplog):
        class BrokenProvider:
            provider_name = "test:broken"

            def refine_reasons(self, request_context, items):
                raise TimeoutError("upstream timeout")

        original = _sample_items()
        with caplog.at_level("WARNING", logger="travel_agent.agents.llm"):
            enriched = LlmRationaleDecorator(BrokenProvider()).enrich({}, original)
        assert enriched == original
        assert all("reasonSource" not in row for row in enriched)
        assert any("keeping template reasons" in r.message for r in caplog.records)

    def test_empty_items_short_circuit(self):
        class ShouldNotRun:
            provider_name = "test:never"

            def refine_reasons(self, request_context, items):
                raise AssertionError("should not be called")

        assert LlmRationaleDecorator(ShouldNotRun()).enrich({}, []) == []


def test_null_provider_passthrough():
    provider = NullLlmProvider()
    assert provider.refine_reasons({}, _sample_items()) == ["本地口碑", "时段匹配"]
