"""Multi-level cache (fourth-round R3, plan §四.R3).

L1  in-process TTL cache (per-pod, microseconds, absorbs hot repeats)
L2  Redis (existing CacheManager; cluster-capable, shared across pods,
    invalidated via pub/sub broadcast)
L3  semantic cache — handled by the caller (Milvus); this module only
    exposes the layered protocol and hit-rate counters.

Read path:  L1 hit -> return; L1 miss -> L2 hit -> backfill L1; both miss
            -> loader (caller-provided) -> fill L1 + L2.
Write path: caller fills/updates L2 then calls ``invalidate`` which deletes
            L2 keys and broadcasts a channel message so every pod drops its
            L1 copy (no stale-window dependency on L1 TTL alone).

All Redis/network operations are fail-open: a cache outage degrades to the
loader (origin), never breaks the request path (lesson from the kind
staging retest: telemetry/side effects must not 500 user requests).
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from typing import Any, Awaitable, Callable

try:
    from cachetools import TTLCache

    _HAS_CACHETOOLS = True
except ImportError:  # pragma: no cover - cachetools is a hard dep in requirements
    _HAS_CACHETOOLS = False


class _SimpleTTLCache:
    """Minimal TTL cache used when cachetools is unavailable."""

    def __init__(self, maxsize: int, ttl: float) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            row = self._data.get(key)
            if row is None:
                return None
            expires, value = row
            if time.monotonic() > expires:
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self._maxsize:
                # drop oldest insert (approximate LRU)
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]
            self._data[key] = (time.monotonic() + self._ttl, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class _TTLCacheFacade:
    """cachetools.TTLCache uses item access; unify on get/set/delete/clear."""

    def __init__(self, maxsize: int, ttl: float) -> None:
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)

    def get(self, key: str) -> Any:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def delete(self, key: str) -> None:
        try:
            del self._cache[key]
        except KeyError:
            pass

    def clear(self) -> None:
        self._cache.clear()


def _build_l1() -> Any:
    size = int(os.getenv("TRAVEL_L1_CACHE_SIZE", "2048"))
    ttl = float(os.getenv("TRAVEL_L1_CACHE_TTL_SECONDS", "5"))
    if _HAS_CACHETOOLS:
        return _TTLCacheFacade(size, ttl)
    return _SimpleTTLCache(size, ttl)


class MultiLevelCache:
    """L1(process) + L2(Redis) cache with invalidation broadcast."""

    INVALIDATE_CHANNEL = "travel-cache-invalidate"

    def __init__(self, redis_client: Any = None) -> None:
        self._l1 = _build_l1()
        self._redis = redis_client
        self._listener_task: asyncio.Task | None = None
        self._counters = {"l1_hit": 0, "l2_hit": 0, "miss": 0, "invalidate": 0}
        if self._redis is not None:
            self._start_listener()

    # -- metrics ----------------------------------------------------------
    @property
    def counters(self) -> dict[str, int]:
        return dict(self._counters)

    def prometheus_metrics(self) -> str:
        total = self._counters["l1_hit"] + self._counters["l2_hit"] + self._counters["miss"]
        hit_rate = (
            (self._counters["l1_hit"] + self._counters["l2_hit"]) / total if total else 0.0
        )
        return (
            f"travel_cache_l1_hits_total {self._counters['l1_hit']}\n"
            f"travel_cache_l2_hits_total {self._counters['l2_hit']}\n"
            f"travel_cache_misses_total {self._counters['miss']}\n"
            f"travel_cache_invalidations_total {self._counters['invalidate']}\n"
            f"travel_cache_hit_rate {hit_rate:.4f}\n"
        )

    # -- read path ---------------------------------------------------------
    def l1_get(self, key: str) -> Any:
        """Synchronous L1 probe for sync callers (never awaits)."""
        return self._l1.get(key)

    def l1_put(self, key: str, value: Any) -> None:
        self._l1.set(key, value)

    async def get_or_load(
        self,
        key: str,
        loader: Callable[[], Awaitable[Any]],
        ttl_seconds: int = 60,
        serializer: Callable[[Any], str] | None = None,
        deserializer: Callable[[str], Any] | None = None,
    ) -> Any:
        value = self._l1.get(key)
        if value is not None:
            self._counters["l1_hit"] += 1
            return value
        if self._redis is not None:
            try:
                raw = await self._redis.get(key)
            except Exception:
                raw = None
            if raw is not None:
                self._counters["l2_hit"] += 1
                value = deserializer(raw) if deserializer else _default_deserialize(raw)
                self._l1.set(key, value)
                return value
        self._counters["miss"] += 1
        value = await loader()
        self._store(key, value, ttl_seconds, serializer)
        return value

    def _store(
        self,
        key: str,
        value: Any,
        ttl_seconds: int,
        serializer: Callable[[Any], str] | None = None,
    ) -> None:
        self._l1.set(key, value)
        if self._redis is None:
            return
        try:
            raw = serializer(value) if serializer else _default_serialize(value)
            # per-key jitter (existing CacheManager convention, anti-stampede)
            import random

            jittered = int(ttl_seconds * (1.0 + random.uniform(0, 0.1)))
            self._redis.setex(key, jittered, raw)
        except Exception:
            pass  # fail-open

    # -- write path ---------------------------------------------------------
    async def invalidate(self, *keys: str) -> None:
        self._counters["invalidate"] += len(keys)
        for key in keys:
            self._l1.delete(key)
        if self._redis is None:
            return
        try:
            pipe = self._redis.pipeline(transaction=False)
            for key in keys:
                pipe.delete(key)
            pipe.publish(self.INVALIDATE_CHANNEL, json.dumps(keys))
            await pipe.execute()
        except Exception:
            pass  # fail-open

    # -- L1 broadcast listener ------------------------------------------------
    def _start_listener(self) -> None:
        try:
            self._listener_task = asyncio.get_running_loop().create_task(
                self._listen_invalidate()
            )
        except RuntimeError:
            # no running loop (module import time) — start lazily on first use
            self._listener_task = None

    async def ensure_listener(self) -> None:
        if self._redis is not None and self._listener_task is None:
            self._start_listener()

    async def _listen_invalidate(self) -> None:
        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(self.INVALIDATE_CHANNEL)
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    keys = json.loads(message.get("data", "[]"))
                except Exception:
                    continue
                for key in keys if isinstance(keys, list) else []:
                    self._l1.delete(key)
        except Exception:
            return  # listener is best-effort


def _default_serialize(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _default_deserialize(raw: Any) -> Any:
    return json.loads(raw)
