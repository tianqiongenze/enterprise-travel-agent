"""Module provides service components and helpers."""

import json
import inspect
import os
import random
import time
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

# Redis cluster URL example: redis://127.0.0.1:7000
REDIS_URL = os.getenv("TRAVEL_REDIS_URL", "redis://127.0.0.1:7000")
REDIS_MODE = os.getenv("TRAVEL_REDIS_MODE", "cluster").strip().lower()


def _cluster_client_kwargs(max_connections: int) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "encoding": "utf-8",
        "decode_responses": True,
        "max_connections": max_connections,
    }
    try:
        params = inspect.signature(redis.RedisCluster.__init__).parameters
    except Exception:
        params = {}
    if "skip_full_coverage_check" in params:
        kwargs["skip_full_coverage_check"] = True
    elif "require_full_coverage" in params:
        kwargs["require_full_coverage"] = False
    return kwargs


class CacheManager:
    """
    企业级缓存管理器：
    - 热点目的地攻略缓存
    - 用户限流
    - 分布式锁
    - 幂等去重
    - 会话画像缓存
    """

    def __init__(self):
        max_connections = int(os.getenv("TRAVEL_REDIS_MAX_CONNECTIONS", "800"))
        self.redis_client = self._build_client(max_connections)

    def _build_client(self, max_connections: int):
        if REDIS_MODE in {"cluster", "redis_cluster", "redis-cluster"}:
            try:
                return redis.RedisCluster.from_url(REDIS_URL, **_cluster_client_kwargs(max_connections))
            except Exception as error:
                print(f"[cache-manager] redis cluster init failed, fallback single: {error}")
        return redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=max_connections,
        )

    async def get_hot_destination_plan(self, destination: str) -> Optional[dict]:
        key = f"hot_plan:{destination}"
        data = await self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_hot_destination_plan(self, destination: str, plan_dict: dict, ttl: int = 3600 * 24):
        key = f"hot_plan:{destination}"
        fuzzed_ttl = ttl + random.randint(60, 1200)
        await self.redis_client.setex(key, fuzzed_ttl, json.dumps(plan_dict, ensure_ascii=False))

    async def is_rate_limited(self, user_id: str, limit: int = 10, window_sec: int = 60) -> bool:
        key = f"rate_limit:user:{user_id}"
        current = await self.redis_client.get(key)
        if current and int(current) >= limit:
            return True
        await self.redis_client.incr(key)
        await self.redis_client.expire(key, window_sec)
        return False

    async def set_user_profile_cache(self, tenant_id: str, user_id: str, profile: Dict[str, Any], ttl: int = 3600) -> None:
        key = f"profile:{tenant_id}:{user_id}"
        await self.redis_client.setex(key, ttl, json.dumps(profile, ensure_ascii=False))

    async def get_user_profile_cache(self, tenant_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        key = f"profile:{tenant_id}:{user_id}"
        data = await self.redis_client.get(key)
        if not data:
            return None
        return json.loads(data)

    async def is_idempotency_replayed(self, tenant_id: str, idempotency_key: str, ttl: int = 600) -> bool:
        key = f"idempotency:{tenant_id}:{idempotency_key}"
        created = await self.redis_client.set(key, str(int(time.time())), ex=ttl, nx=True)
        return not bool(created)

    async def try_distributed_lock(self, lock_name: str, owner_id: str, ttl_sec: int = 20) -> bool:
        key = f"lock:{lock_name}"
        ok = await self.redis_client.set(key, owner_id, ex=ttl_sec, nx=True)
        return bool(ok)

    async def release_distributed_lock(self, lock_name: str, owner_id: str) -> bool:
        key = f"lock:{lock_name}"
        current = await self.redis_client.get(key)
        if current != owner_id:
            return False
        await self.redis_client.delete(key)
        return True

    def _tenant_slot(self, tenant_id: str) -> str:
        return "{tenant:%s}" % tenant_id

    async def set_itinerary_snapshot(
        self,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        itinerary: Dict[str, Any],
        ttl: int = 3600 * 12,
    ) -> None:
        slot = self._tenant_slot(tenant_id)
        key = f"itinerary:{slot}:{user_id}:{conversation_id}"
        await self.redis_client.setex(key, ttl, json.dumps(itinerary, ensure_ascii=False))

    async def get_itinerary_snapshot(self, tenant_id: str, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        slot = self._tenant_slot(tenant_id)
        key = f"itinerary:{slot}:{user_id}:{conversation_id}"
        data = await self.redis_client.get(key)
        if not data:
            return None
        return json.loads(data)

    async def incr_city_popularity(self, city: str, ttl: int = 3600 * 24 * 30) -> int:
        key = f"city_popularity:{city}"
        value = await self.redis_client.incr(key)
        await self.redis_client.expire(key, ttl)
        return int(value)

    async def get_city_popularity(self, city: str) -> int:
        key = f"city_popularity:{city}"
        value = await self.redis_client.get(key)
        return int(value) if value is not None else 0

    async def push_recent_search(self, tenant_id: str, user_id: str, query: Dict[str, Any], max_len: int = 20) -> None:
        slot = self._tenant_slot(tenant_id)
        key = f"recent_search:{slot}:{user_id}"
        await self.redis_client.lpush(key, json.dumps(query, ensure_ascii=False))
        await self.redis_client.ltrim(key, 0, max(0, max_len - 1))
        await self.redis_client.expire(key, 3600 * 24 * 7)

    async def get_recent_searches(self, tenant_id: str, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        slot = self._tenant_slot(tenant_id)
        key = f"recent_search:{slot}:{user_id}"
        rows = await self.redis_client.lrange(key, 0, max(0, limit - 1))
        items: List[Dict[str, Any]] = []
        for row in rows:
            try:
                value = json.loads(row)
            except Exception:
                continue
            if isinstance(value, dict):
                items.append(value)
        return items


cache_manager = CacheManager()

