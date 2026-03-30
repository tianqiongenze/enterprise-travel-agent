"""Module provides service components and helpers."""

import importlib
import inspect
import os
import time


class TrafficGuard:
    def __init__(self) -> None:
        self._client = None
        redis_url = os.getenv("TRAVEL_GUARD_REDIS_URL", os.getenv("TRAVEL_REDIS_URL", "")).strip()
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

    def allow_request(self, scope: str) -> bool:
        limit = int(os.getenv("TRAVEL_RATE_LIMIT_PER_MINUTE", "200"))
        window = int(os.getenv("TRAVEL_RATE_LIMIT_WINDOW_SEC", "60"))
        if self._client is None:
            return True
        key = f"guard:rate:{scope}"
        try:
            value = self._client.incr(key)
            if int(value) == 1:
                self._client.expire(key, window)
            return int(value) <= limit
        except Exception:
            return True

    def claim_idempotency(self, tenant_id: str, idem_key: str) -> bool:
        ttl = int(os.getenv("TRAVEL_IDEMPOTENCY_TTL_SEC", "900"))
        if self._client is None:
            return True
        key = f"guard:idempotency:{{tenant:{tenant_id}}}:{idem_key}"
        try:
            created = self._client.set(key, str(int(time.time())), ex=ttl, nx=True)
            return bool(created)
        except Exception:
            return True

    def allow_circuit(self, circuit_name: str) -> bool:
        if self._client is None:
            return True
        key = f"guard:circuit:{circuit_name}:open_until"
        try:
            value = self._client.get(key)
            if value is None:
                return True
            return float(value) <= time.time()
        except Exception:
            return True

    def record_success(self, circuit_name: str) -> None:
        if self._client is None:
            return
        try:
            self._client.delete(f"guard:circuit:{circuit_name}:failures")
            self._client.delete(f"guard:circuit:{circuit_name}:open_until")
        except Exception:
            return

    def record_failure(self, circuit_name: str) -> None:
        if self._client is None:
            return
        threshold = int(os.getenv("TRAVEL_CIRCUIT_FAIL_THRESHOLD", "5"))
        cooldown = int(os.getenv("TRAVEL_CIRCUIT_COOLDOWN_SEC", "30"))
        fail_key = f"guard:circuit:{circuit_name}:failures"
        open_key = f"guard:circuit:{circuit_name}:open_until"
        try:
            failures = int(self._client.incr(fail_key))
            self._client.expire(fail_key, cooldown)
            if failures >= threshold:
                self._client.setex(open_key, cooldown, str(time.time() + cooldown))
        except Exception:
            return

