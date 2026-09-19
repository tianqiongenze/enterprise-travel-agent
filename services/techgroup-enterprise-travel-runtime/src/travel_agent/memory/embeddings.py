"""Pluggable text-embedding providers for the vector memory layer.

Selection (``TRAVEL_EMBEDDING_BACKEND``):

- ``auto`` (default): try the local sentence-transformers model, then the
  DashScope embedding API (when an API key is configured), then fall back to
  the deterministic hash provider with a loud warning. The fallback is always
  explicit: ``provider_name`` becomes ``hash-fallback`` and a warning is
  logged, so deployments can gate on real semantic retrieval.
- ``hash``: force the deterministic token-bucket provider (tests/offline).
- ``local-model``: force the local model; hard failure when unavailable.
- ``dashscope``: force the remote API; hard failure when unavailable.

``TRAVEL_EMBEDDING_DIM`` must match the provider output dimension (defaults:
512 for bge-small-zh-v1.5, 1024 for DashScope text-embedding-v3, 64 for hash).
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import List, Protocol

logger = logging.getLogger("travel_agent.memory.embeddings")

DEFAULT_LOCAL_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_LOCAL_DIM = 512
DEFAULT_DASHSCOPE_MODEL = "text-embedding-v3"
DEFAULT_DASHSCOPE_DIM = 1024
DEFAULT_HASH_DIM = 64


class EmbeddingProvider(Protocol):
    def dim(self) -> int: ...

    def embed(self, text: str) -> List[float]: ...

    @property
    def provider_name(self) -> str: ...


class HashEmbeddingProvider:
    """Deterministic token-bucket vectors. Lexical overlap, NOT semantic."""

    def __init__(self, dim: int = DEFAULT_HASH_DIM) -> None:
        self._dim = int(os.getenv("TRAVEL_VECTOR_DIM", str(dim)))

    @property
    def provider_name(self) -> str:
        return "hash"

    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> List[float]:
        vec = [0.0] * self._dim
        for token in _tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            idx = int(digest[:8], 16) % self._dim
            vec[idx] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        if norm == 0:
            return vec
        return [v / norm for v in vec]


class LocalModelEmbeddingProvider:
    """sentence-transformers model (default BAAI/bge-small-zh-v1.5), lazy-loaded."""

    def __init__(self) -> None:
        self._model_name = os.getenv("TRAVEL_EMBEDDING_LOCAL_MODEL", DEFAULT_LOCAL_MODEL)
        self._dim = int(os.getenv("TRAVEL_EMBEDDING_DIM", str(DEFAULT_LOCAL_DIM)))
        self._model = None

    @property
    def provider_name(self) -> str:
        return f"local-model:{self._model_name}"

    def dim(self) -> int:
        return self._dim

    def _load(self):
        if self._model is None:
            sentence_transformers = importlib_import("sentence_transformers")
            self._model = sentence_transformers.SentenceTransformer(self._model_name)
        return self._model

    def embed(self, text: str) -> List[float]:
        model = self._load()
        vector = model.encode(text, normalize_embeddings=True)
        vector = [float(x) for x in vector]
        if len(vector) != self._dim:
            raise RuntimeError(
                f"embedding dim mismatch: model {self._model_name} returned "
                f"{len(vector)}, TRAVEL_EMBEDDING_DIM={self._dim}"
            )
        return vector


class DashScopeEmbeddingProvider:
    """DashScope text-embedding API (requires AI_DASHSCOPE_API_KEY)."""

    def __init__(self) -> None:
        self._model = os.getenv("TRAVEL_EMBEDDING_REMOTE_MODEL", DEFAULT_DASHSCOPE_MODEL)
        self._dim = int(os.getenv("TRAVEL_EMBEDDING_DIM", str(DEFAULT_DASHSCOPE_DIM)))
        self._endpoint = os.getenv(
            "TRAVEL_EMBEDDING_ENDPOINT",
            "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding",
        )

    @property
    def provider_name(self) -> str:
        return f"dashscope:{self._model}"

    def dim(self) -> int:
        return self._dim

    def _api_key(self) -> str:
        key = os.getenv("AI_DASHSCOPE_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")).strip()
        if not key:
            raise RuntimeError("DashScope embedding selected but AI_DASHSCOPE_API_KEY is not set")
        return key

    def embed(self, text: str) -> List[float]:
        import requests

        response = requests.post(
            self._endpoint,
            headers={"Authorization": f"Bearer {self._api_key()}"},
            json={
                "model": self._model,
                "input": {"texts": [text]},
                "parameters": {"dimension": self._dim, "text_type": "query"},
            },
            timeout=float(os.getenv("TRAVEL_EMBEDDING_TIMEOUT_SEC", "5.0")),
        )
        if response.status_code != 200:
            raise RuntimeError(f"dashscope embedding failed: {response.status_code} {response.text[:200]}")
        embeddings = response.json().get("output", {}).get("embeddings", [])
        if not embeddings:
            raise RuntimeError("dashscope embedding returned no embeddings")
        vector = [float(x) for x in embeddings[0].get("embedding", [])]
        if len(vector) != self._dim:
            raise RuntimeError(
                f"embedding dim mismatch: dashscope returned {len(vector)}, expected {self._dim}"
            )
        return vector


def importlib_import(name: str):
    import importlib

    return importlib.import_module(name)


def _tokenize(text: str) -> List[str]:
    cleaned = text.lower().replace("{", " ").replace("}", " ").replace('"', " ")
    return [part for part in cleaned.split() if part]


def _hash_warning(provider: "HashEmbeddingProvider", reason: str) -> HashEmbeddingProvider:
    logger.warning(
        "semantic embeddings unavailable (%s); using hash-fallback provider '%s' "
        "which is lexical overlap only - install sentence-transformers (local) or "
        "set AI_DASHSCOPE_API_KEY (remote) for real retrieval",
        reason,
        provider.provider_name,
    )
    return provider


def create_embedding_provider() -> EmbeddingProvider:
    backend = os.getenv("TRAVEL_EMBEDDING_BACKEND", "auto").strip().lower()
    if backend == "hash":
        return HashEmbeddingProvider()
    if backend == "local-model":
        return LocalModelEmbeddingProvider()
    if backend == "dashscope":
        return DashScopeEmbeddingProvider()

    # auto: local model first, then DashScope, then explicit hash fallback.
    try:
        provider = LocalModelEmbeddingProvider()
        importlib_import("sentence_transformers")
        return provider
    except Exception as local_error:
        local_reason = str(local_error)
    has_remote_key = bool(os.getenv("AI_DASHSCOPE_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")).strip())
    if has_remote_key:
        return DashScopeEmbeddingProvider()
    return _hash_warning(HashEmbeddingProvider(), f"local model unavailable: {local_reason}")
