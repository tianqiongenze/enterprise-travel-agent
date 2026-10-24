"""Contract tests for DashScopeEmbeddingProvider against a local fake
OpenAI/DashScope-compatible HTTP endpoint (no external network needed).

Covers the wire contract: bearer auth header, request body shape
(model/input.texts/parameters.dimension), and response parsing
(output.embeddings[0].embedding), plus dim-mismatch and HTTP error handling.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.travel_agent.memory.embeddings import DashScopeEmbeddingProvider


class _FakeEmbeddingsHandler(BaseHTTPRequestHandler):
    """Echoes a DashScope-style /embeddings response; records the last request."""

    last_request: dict = {}
    last_auth: str = ""
    status_code: int = 200
    response_body: dict = {}

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        _FakeEmbeddingsHandler.last_request = json.loads(self.rfile.read(length) or b"{}")
        _FakeEmbeddingsHandler.last_auth = self.headers.get("Authorization", "")
        self.send_response(_FakeEmbeddingsHandler.status_code)
        self.send_header("Content-Type", "application/json")
        body = json.dumps(_FakeEmbeddingsHandler.response_body).encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # silence
        return


@pytest.fixture()
def fake_embeddings_server(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _FakeEmbeddingsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/api/v1/services/embeddings/text-embedding/text-embedding"
    monkeypatch.setenv("TRAVEL_EMBEDDING_ENDPOINT", url)
    monkeypatch.setenv("AI_DASHSCOPE_API_KEY", "sk-fake-test-key")
    yield server
    server.shutdown()


def test_dashscope_provider_wire_contract(fake_embeddings_server, monkeypatch):
    monkeypatch.setenv("TRAVEL_EMBEDDING_DIM", "8")
    _FakeEmbeddingsHandler.status_code = 200
    _FakeEmbeddingsHandler.response_body = {
        "output": {"embeddings": [{"embedding": [0.1] * 8, "text_index": 0}]},
        "usage": {"total_tokens": 5},
        "request_id": "fake-1",
    }
    provider = DashScopeEmbeddingProvider()
    vector = provider.embed("杭州 酒店")
    assert len(vector) == 8
    assert vector == [0.1] * 8
    assert _FakeEmbeddingsHandler.last_auth == "Bearer sk-fake-test-key"
    body = _FakeEmbeddingsHandler.last_request
    assert body["model"] == provider.provider_name.split(":", 1)[1]
    assert body["input"]["texts"] == ["杭州 酒店"]
    assert body["parameters"]["dimension"] == 8
    assert body["parameters"]["text_type"] == "query"


def test_dashscope_provider_dim_mismatch_rejected(fake_embeddings_server, monkeypatch):
    monkeypatch.setenv("TRAVEL_EMBEDDING_DIM", "8")
    _FakeEmbeddingsHandler.status_code = 200
    _FakeEmbeddingsHandler.response_body = {
        "output": {"embeddings": [{"embedding": [0.1] * 4}]},
    }
    provider = DashScopeEmbeddingProvider()
    with pytest.raises(RuntimeError, match="dim mismatch"):
        provider.embed(" mismatch")


def test_dashscope_provider_http_error_raises(fake_embeddings_server, monkeypatch):
    _FakeEmbeddingsHandler.status_code = 401
    _FakeEmbeddingsHandler.response_body = {"code": "InvalidApiKey", "message": "bad key"}
    provider = DashScopeEmbeddingProvider()
    with pytest.raises(RuntimeError, match="401"):
        provider.embed("x")


def test_dashscope_provider_missing_key_raises(fake_embeddings_server, monkeypatch):
    monkeypatch.delenv("AI_DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    provider = DashScopeEmbeddingProvider()
    with pytest.raises(RuntimeError, match="AI_DASHSCOPE_API_KEY"):
        provider.embed("x")
