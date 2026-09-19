"""Module provides memory backends and access helpers."""

import hashlib
import importlib
import os
from typing import Dict, List, Tuple

from .base import MemoryStore


def _tokenize(text: str) -> List[str]:
    cleaned = text.lower().replace("{", " ").replace("}", " ").replace('"', " ")
    return [part for part in cleaned.split() if part]


def _similarity_score(tokens: List[str], query_tokens: List[str]) -> int:
    if not query_tokens:
        return 0
    token_set = set(tokens)
    query_set = set(query_tokens)
    return len(token_set.intersection(query_set))


def _hash_vector(text: str, dim: int = 64) -> List[float]:
    vec = [0.0] * dim
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % dim
        vec[idx] += 1.0
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return vec
    return [v / norm for v in vec]


class _LocalVectorBackend:
    def __init__(self) -> None:
        self._rows: Dict[str, List[str]] = {}

    def append(self, key: str, message: str) -> None:
        self._rows.setdefault(key, []).append(message)

    def read(self, key: str, limit: int) -> List[str]:
        rows = self._rows.get(key, [])
        return rows[-limit:]

    def query(self, key: str, query: str, limit: int) -> List[str]:
        rows = self._rows.get(key, [])
        if not rows:
            return []
        query_tokens = _tokenize(query)
        scored: List[Tuple[int, str]] = []
        for row in rows:
            score = _similarity_score(_tokenize(row), query_tokens)
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit] if item[0] > 0]


class _QdrantVectorBackend:
    def __init__(self) -> None:
        import requests

        self.requests = requests
        self.url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
        self.collection = os.getenv("TRAVEL_VECTOR_COLLECTION", "travel_agent_memory")
        self.dim = int(os.getenv("TRAVEL_VECTOR_DIM", "64"))
        self.timeout = float(os.getenv("TRAVEL_VECTOR_TIMEOUT_SEC", "2.0"))
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        endpoint = f"{self.url}/collections/{self.collection}"
        payload = {
            "vectors": {
                "size": self.dim,
                "distance": "Cosine",
            }
        }
        response = self.requests.put(endpoint, json=payload, timeout=self.timeout)
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"qdrant collection init failed: {response.status_code} {response.text}")

    def append(self, key: str, message: str) -> None:
        vector = _hash_vector(message, self.dim)
        point_id = int(hashlib.sha256(f"{key}:{message}".encode("utf-8")).hexdigest()[:16], 16)
        endpoint = f"{self.url}/collections/{self.collection}/points"
        payload = {
            "points": [
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": {
                        "memory_key": key,
                        "text": message,
                    },
                }
            ]
        }
        response = self.requests.put(endpoint, json=payload, timeout=self.timeout)
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"qdrant append failed: {response.status_code} {response.text}")

    def read(self, key: str, limit: int) -> List[str]:
        endpoint = f"{self.url}/collections/{self.collection}/points/scroll"
        payload = {
            "limit": limit,
            "with_payload": True,
            "filter": {
                "must": [
                    {
                        "key": "memory_key",
                        "match": {"value": key},
                    }
                ]
            },
        }
        response = self.requests.post(endpoint, json=payload, timeout=self.timeout)
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"qdrant read failed: {response.status_code} {response.text}")
        rows = response.json().get("result", {}).get("points", [])
        return [row.get("payload", {}).get("text", "") for row in rows if row.get("payload", {}).get("text")]

    def query(self, key: str, query: str, limit: int) -> List[str]:
        endpoint = f"{self.url}/collections/{self.collection}/points/search"
        payload = {
            "vector": _hash_vector(query, self.dim),
            "limit": limit,
            "with_payload": True,
            "filter": {
                "must": [
                    {
                        "key": "memory_key",
                        "match": {"value": key},
                    }
                ]
            },
        }
        response = self.requests.post(endpoint, json=payload, timeout=self.timeout)
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"qdrant query failed: {response.status_code} {response.text}")
        rows = response.json().get("result", [])
        return [row.get("payload", {}).get("text", "") for row in rows if row.get("payload", {}).get("text")]


class _MilvusVectorBackend:
    def __init__(self) -> None:
        pymilvus = importlib.import_module("pymilvus")
        Collection = getattr(pymilvus, "Collection")
        CollectionSchema = getattr(pymilvus, "CollectionSchema")
        DataType = getattr(pymilvus, "DataType")
        FieldSchema = getattr(pymilvus, "FieldSchema")
        connections = getattr(pymilvus, "connections")
        utility = getattr(pymilvus, "utility")

        self.dim = int(os.getenv("TRAVEL_VECTOR_DIM", "64"))
        self.collection_name = os.getenv("TRAVEL_VECTOR_COLLECTION", "travel_agent_memory")
        host = os.getenv("MILVUS_HOST", "127.0.0.1")
        port = os.getenv("MILVUS_PORT", "19530")

        connections.connect(alias="default", host=host, port=port)
        if not utility.has_collection(self.collection_name):
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="memory_key", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
            ]
            schema = CollectionSchema(fields=fields, description="travel agent memory vectors")
            collection = Collection(name=self.collection_name, schema=schema)
            collection.create_index("vector", {
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE",
                "params": {"nlist": 128},
            })
        self.collection = Collection(self.collection_name)
        self.collection.load()

    def append(self, key: str, message: str) -> None:
        point_id = int(hashlib.sha256(f"{key}:{message}".encode("utf-8")).hexdigest()[:16], 16)
        data = [[point_id], [key], [message], [_hash_vector(message, self.dim)]]
        self.collection.insert(data)
        self.collection.flush()

    def read(self, key: str, limit: int) -> List[str]:
        rows = self.collection.query(
            expr=f'memory_key == "{key}"',
            output_fields=["text"],
            limit=limit,
        )
        return [row.get("text", "") for row in rows if row.get("text")]

    def query(self, key: str, query: str, limit: int) -> List[str]:
        params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        rows = self.collection.search(
            data=[_hash_vector(query, self.dim)],
            anns_field="vector",
            param=params,
            limit=limit,
            expr=f'memory_key == "{key}"',
            output_fields=["text"],
        )
        if not rows:
            return []
        return [hit.entity.get("text") for hit in rows[0] if hit.entity and hit.entity.get("text")]


class _FaissVectorBackend:
    def __init__(self) -> None:
        self.faiss = importlib.import_module("faiss")
        self.dim = int(os.getenv("TRAVEL_VECTOR_DIM", "64"))
        self.index = self.faiss.IndexFlatIP(self.dim)
        self._meta: List[Tuple[str, str]] = []

    def append(self, key: str, message: str) -> None:
        vector = _hash_vector(message, self.dim)
        np = importlib.import_module("numpy")
        matrix = np.array([vector], dtype="float32")
        self.index.add(matrix)
        self._meta.append((key, message))

    def read(self, key: str, limit: int) -> List[str]:
        rows = [item[1] for item in self._meta if item[0] == key]
        return rows[-limit:]

    def query(self, key: str, query: str, limit: int) -> List[str]:
        if self.index.ntotal == 0:
            return []
        np = importlib.import_module("numpy")
        vector = np.array([_hash_vector(query, self.dim)], dtype="float32")
        distances, indices = self.index.search(vector, max(1, limit * 4))
        _ = distances
        rows: List[str] = []
        for idx in indices[0].tolist():
            if idx < 0 or idx >= len(self._meta):
                continue
            row_key, text = self._meta[idx]
            if row_key != key:
                continue
            rows.append(text)
            if len(rows) >= limit:
                break
        return rows


class VectorMemoryStore(MemoryStore):
    def __init__(self) -> None:
        backend = os.getenv("TRAVEL_VECTOR_BACKEND", "faiss").strip().lower()
        strict = os.getenv("TRAVEL_VECTOR_STRICT", "true").strip().lower() == "true"
        if backend in {"", "local"}:
            self.backend = _LocalVectorBackend()
            self.backend_name = "local"
            return
        try:
            if backend == "qdrant":
                self.backend = _QdrantVectorBackend()
                self.backend_name = "qdrant"
                return
            if backend == "milvus":
                self.backend = _MilvusVectorBackend()
                self.backend_name = "milvus"
                return
            if backend == "faiss":
                self.backend = _FaissVectorBackend()
                self.backend_name = "faiss"
                return
            raise RuntimeError(f"Unsupported TRAVEL_VECTOR_BACKEND: {backend}")
        except Exception as error:
            if strict:
                raise RuntimeError(f"TRAVEL_VECTOR_BACKEND={backend} init failed: {error}") from error
            print(f"[vector-store] {backend} unavailable, fallback to local: {error}")
            self.backend = _LocalVectorBackend()
            self.backend_name = "local"

    def append_message(self, key: str, message: str) -> None:
        self.backend.append(key, message)

    def read_messages(self, key: str, limit: int = 50) -> List[str]:
        return self.backend.read(key, limit)

    def query_messages(self, key: str, query: str, limit: int = 10) -> List[str]:
        return self.backend.query(key, query, limit)
