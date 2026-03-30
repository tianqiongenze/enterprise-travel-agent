"""Module provides memory backends and access helpers."""

import importlib
import inspect
import os
from typing import Any, List, Optional, cast

try:
    redis_module: Optional[Any] = importlib.import_module("redis")
except ImportError:
    redis_module = None

from .base import MemoryStore


class RedisMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self.redis_url = os.getenv("TRAVEL_REDIS_URL", os.getenv("REDIS_URL", "")).strip()
        self.redis_mode = os.getenv("TRAVEL_REDIS_MODE", "cluster").strip().lower()
        self.enabled = bool(self.redis_url and redis_module is not None)
        self._client: Optional[Any] = None
        self._ttl = int(os.getenv("TRAVEL_MEMORY_TTL_SECONDS", "86400"))

        if not self.enabled:
            return

        module = cast(Any, redis_module)
        max_connections = int(os.getenv("TRAVEL_REDIS_MAX_CONNECTIONS", "500"))
        try:
            if self.redis_mode in {"cluster", "redis-cluster", "redis_cluster"}:
                cluster_kwargs: dict[str, Any] = {
                    "decode_responses": True,
                    "max_connections": max_connections,
                }
                try:
                    params = inspect.signature(module.RedisCluster.__init__).parameters
                except Exception:
                    params = {}
                if "skip_full_coverage_check" in params:
                    cluster_kwargs["skip_full_coverage_check"] = True
                elif "require_full_coverage" in params:
                    cluster_kwargs["require_full_coverage"] = False
                self._client = module.RedisCluster.from_url(self.redis_url, **cluster_kwargs)
            else:
                self._client = module.Redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    max_connections=max_connections,
                )
        except Exception as error:
            # Fallback to single-node mode if cluster parsing fails.
            try:
                self._client = module.Redis.from_url(self.redis_url, decode_responses=True)
            except Exception:
                print(f"[redis-memory] init failed: {error}")
                self.enabled = False
                self._client = None

    def append_message(self, key: str, message: str) -> None:
        if not self.enabled or self._client is None:
            return
        client = self._client
        if not hasattr(client, "rpush"):
            return
        client.rpush(key, message)
        if self._ttl > 0 and hasattr(client, "expire"):
            client.expire(key, self._ttl)

    def read_messages(self, key: str, limit: int = 50) -> List[str]:
        if not self.enabled or self._client is None:
            return []
        start = max(0, -limit)
        client = self._client
        if not hasattr(client, "lrange"):
            return []
        return list(client.lrange(key, start, -1))
