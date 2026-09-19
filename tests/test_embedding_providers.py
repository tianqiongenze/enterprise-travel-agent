"""Unit tests for embedding provider selection (memory/embeddings.py)."""

import hashlib
import os

import pytest

from src.travel_agent.memory.embeddings import (
    DashScopeEmbeddingProvider,
    HashEmbeddingProvider,
    LocalModelEmbeddingProvider,
    create_embedding_provider,
)


@pytest.fixture(autouse=True)
def _restore_embedding_env(monkeypatch):
    keys = [
        "TRAVEL_EMBEDDING_BACKEND",
        "TRAVEL_EMBEDDING_DIM",
        "TRAVEL_VECTOR_DIM",
        "TRAVEL_EMBEDDING_LOCAL_MODEL",
        "TRAVEL_EMBEDDING_REMOTE_MODEL",
        "TRAVEL_EMBEDDING_ENDPOINT",
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


class TestHashProvider:
    def test_deterministic_normalized(self):
        p = HashEmbeddingProvider()
        a, b = p.embed("杭州 酒店 家庭"), p.embed("杭州 酒店 家庭")
        assert a == b
        assert len(a) == p.dim()
        norm = sum(v * v for v in a) ** 0.5
        assert norm == pytest.approx(1.0, abs=1e-6)

    def test_empty_text_zero_vector(self):
        p = HashEmbeddingProvider()
        assert p.embed("　") == [0.0] * p.dim()

    def test_env_dim_override(self, monkeypatch):
        monkeypatch.setenv("TRAVEL_VECTOR_DIM", "128")
        assert HashEmbeddingProvider().dim() == 128


class TestProviderSelection:
    def test_backend_hash_forced(self, monkeypatch):
        monkeypatch.setenv("TRAVEL_EMBEDDING_BACKEND", "hash")
        assert isinstance(create_embedding_provider(), HashEmbeddingProvider)

    def test_backend_dashscope_forced_with_key(self, monkeypatch):
        monkeypatch.setenv("TRAVEL_EMBEDDING_BACKEND", "dashscope")
        monkeypatch.setenv("AI_DASHSCOPE_API_KEY", "sk-test")
        p = create_embedding_provider()
        assert isinstance(p, DashScopeEmbeddingProvider)
        assert p.dim() == 1024

    def test_auto_without_sentence_transformers_falls_back_to_hash_with_warning(self, monkeypatch, caplog):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "sentence_transformers":
                raise ImportError("not installed in test env")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        with caplog.at_level("WARNING", logger="travel_agent.memory.embeddings"):
            p = create_embedding_provider()
        assert isinstance(p, HashEmbeddingProvider)
        assert any("hash-fallback" in r.message or "lexical" in r.message for r in caplog.records)

    def test_local_model_dim_mismatch_raises(self, monkeypatch):
        monkeypatch.setenv("TRAVEL_EMBEDDING_DIM", "999")
        provider = LocalModelEmbeddingProvider()

        class FakeModel:
            def encode(self, text, normalize_embeddings=False):
                return [0.1] * 512

        provider._model = FakeModel()
        with pytest.raises(RuntimeError, match="dim mismatch"):
            provider.embed("杭州")


class TestDashScopeProvider:
    def test_missing_key_raises(self):
        p = DashScopeEmbeddingProvider()
        with pytest.raises(RuntimeError, match="AI_DASHSCOPE_API_KEY"):
            p.embed("杭州")

    def test_success_and_dim_mismatch(self, monkeypatch):
        monkeypatch.setenv("AI_DASHSCOPE_API_KEY", "sk-test")
        monkeypatch.setenv("TRAVEL_EMBEDDING_DIM", "4")
        p = DashScopeEmbeddingProvider()

        class FakeResponse:
            status_code = 200
            text = ""

            def json(self):
                return {"output": {"embeddings": [{"embedding": [0.1, 0.2, 0.3, 0.4]}]}}

        monkeypatch.setattr(
            "requests.post",
            lambda url, headers=None, json=None, timeout=None: FakeResponse()
            if "dashscope" in url and headers["Authorization"] == "Bearer sk-test"
            else (_ for _ in ()).throw(AssertionError("bad call")),
        )
        assert p.embed("杭州") == [0.1, 0.2, 0.3, 0.4]

        class BadDimResponse(FakeResponse):
            def json(self):
                return {"output": {"embeddings": [{"embedding": [0.1, 0.2]}]}}

        monkeypatch.setattr("requests.post", lambda *a, **kw: BadDimResponse())
        with pytest.raises(RuntimeError, match="dim mismatch"):
            p.embed("杭州")

    def test_http_error_raises(self, monkeypatch):
        monkeypatch.setenv("AI_DASHSCOPE_API_KEY", "sk-test")
        p = DashScopeEmbeddingProvider()

        class FakeResponse:
            status_code = 403
            text = "forbidden"

            def json(self):
                return {}

        monkeypatch.setattr("requests.post", lambda *a, **kw: FakeResponse())
        with pytest.raises(RuntimeError, match="dashscope embedding failed"):
            p.embed("杭州")


def test_hash_tokenization_ignores_braces():
    p = HashEmbeddingProvider(dim=64)
    raw = p.embed('city={"杭州"}')
    assert all(v == 0.0 or abs(v) <= 1.0 for v in raw)
    h = hashlib.sha256("杭州".encode()).hexdigest()
    idx = int(h[:8], 16) % 64
    assert raw[idx] > 0
