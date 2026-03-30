"""Module provides service components and helpers."""

import importlib
import inspect
import os
from typing import Dict, Optional


class MembershipStore:
    def __init__(self) -> None:
        self._memory: Dict[str, str] = {}
        self._client = None
        redis_url = os.getenv("TRAVEL_MEMBERSHIP_REDIS_URL", os.getenv("TRAVEL_REDIS_URL", "")).strip()
        mode = os.getenv("TRAVEL_REDIS_MODE", "cluster").strip().lower()
        if not redis_url:
            return
        try:
            redis_module = importlib.import_module("redis")
            if mode in {"cluster", "redis_cluster", "redis-cluster"}:
                kwargs = {"decode_responses": True}
                try:
                    params = inspect.signature(redis_module.RedisCluster.__init__).parameters
                except Exception:
                    params = {}
                if "skip_full_coverage_check" in params:
                    kwargs["skip_full_coverage_check"] = True
                elif "require_full_coverage" in params:
                    kwargs["require_full_coverage"] = False
                self._client = redis_module.RedisCluster.from_url(redis_url, **kwargs)
            else:
                self._client = redis_module.Redis.from_url(redis_url, decode_responses=True)
        except Exception:
            self._client = None

    def get_tier(self, tenant_id: str, user_id: str) -> Optional[str]:
        key = self._key(tenant_id, user_id)
        if self._client is None:
            return self._memory.get(key)
        try:
            value = self._client.get(key)
            if value:
                return str(value)
        except Exception:
            pass
        return self._memory.get(key)

    def set_tier(self, tenant_id: str, user_id: str, tier: str, ttl_seconds: int = 3600 * 24 * 30) -> None:
        key = self._key(tenant_id, user_id)
        self._memory[key] = tier
        if self._client is None:
            return
        try:
            self._client.setex(key, ttl_seconds, tier)
        except Exception:
            return

    def _key(self, tenant_id: str, user_id: str) -> str:
        return f"membership:{{tenant:{tenant_id}}}:{user_id}"

