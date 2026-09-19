"""Distributed traffic guard: rate limiting, inflight caps, idempotency, circuit breaker.

Semantics (production baseline):
- With Redis available, all limits are enforced cluster-wide.
- Without Redis, or on Redis errors, the guard degrades to a per-process in-memory
  limiter (never a silent fail-open) and logs a warning; ``degraded`` exposes the
  state for metrics/alerting. ``TRAVEL_GUARD_FAIL_CLOSED=true`` (default) denies
  idempotency claims while degraded to preserve at-most-once semantics.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import os
import threading
import time
from collections import deque
from typing import Dict, Optional

logger = logging.getLogger("travel_agent.traffic_guard")

_RATE_KEY_PREFIX = "guard:rate:"
_INFLIGHT_KEY_PREFIX = "guard:inflight:"
_IDEMPOTENCY_KEY_PREFIX = "guard:idempotency:"
_CIRCUIT_KEY_PREFIX = "guard:circuit:"


class TrafficGuard:
    def __init__(self) -> None:
        self._client = None
        self._local_lock = threading.Lock()
        self._local_inflight: Dict[str, int] = {}
        self._local_rate: Dict[str, deque] = {}
        self._local_idempotency: Dict[str, float] = {}
        self._local_circuits: Dict[str, Dict[str, float]] = {}
        self._degraded = True
        redis_url = os.getenv("TRAVEL_GUARD_REDIS_URL", os.getenv("TRAVEL_REDIS_URL", "")).strip()
        mode = os.getenv("TRAVEL_REDIS_MODE", "cluster").strip().lower()
        if not redis_url:
            # Local per-process limits are the designed single-node mode, not a
            # degradation; _degraded stays False so idempotency keeps using the
            # local store as its real store.
            logger.info("traffic guard: no Redis configured; using per-process local limits")
            self._degraded = False
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
            self._degraded = False
        except Exception:
            self._client = None
            logger.exception("traffic guard: Redis init failed; degraded to local limits")

    @property
    def degraded(self) -> bool:
        """True when enforcement is per-process only (no Redis or Redis errors)."""
        return self._client is None or self._degraded

    @property
    def redis_erroring(self) -> bool:
        """True only when Redis was configured but operations are failing."""
        return self._degraded

    @staticmethod
    def _fail_closed() -> bool:
        return os.getenv("TRAVEL_GUARD_FAIL_CLOSED", "true").strip().lower() in {"1", "true", "yes", "on"}

    # ------------------------------------------------------------------ rate
    def allow_request(self, scope: str) -> bool:
        limit = int(os.getenv("TRAVEL_RATE_LIMIT_PER_MINUTE", "200"))
        window = int(os.getenv("TRAVEL_RATE_LIMIT_WINDOW_SEC", "60"))
        key = f"{_RATE_KEY_PREFIX}{scope}"
        if self._client is not None:
            try:
                value = self._client.incr(key)
                if int(value) == 1:
                    self._client.expire(key, window)
                return int(value) <= limit
            except Exception:
                self._enter_degraded("allow_request")
        return self._local_allow_request(scope, limit, window)

    def _local_allow_request(self, scope: str, limit: int, window: int) -> bool:
        now = time.monotonic()
        with self._local_lock:
            hits = self._local_rate.setdefault(scope, deque())
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    # -------------------------------------------------------------- inflight
    def claim_inflight(self, scope: str) -> bool:
        limit = int(os.getenv("TRAVEL_INFLIGHT_LIMIT", "2000"))
        ttl = int(os.getenv("TRAVEL_INFLIGHT_TTL_SEC", "30"))
        if self._client is not None:
            key = f"{_INFLIGHT_KEY_PREFIX}{scope}"
            try:
                current = int(self._client.incr(key))
                self._client.expire(key, ttl)
                if current > limit:
                    self._client.decr(key)
                    return False
                return True
            except Exception:
                self._enter_degraded("claim_inflight")
        local_limit = int(os.getenv("TRAVEL_LOCAL_INFLIGHT_LIMIT", str(limit)))
        with self._local_lock:
            current = int(self._local_inflight.get(scope, 0))
            if current >= local_limit:
                return False
            self._local_inflight[scope] = current + 1
            return True

    def release_inflight(self, scope: str) -> None:
        if self._client is not None:
            key = f"{_INFLIGHT_KEY_PREFIX}{scope}"
            try:
                current = int(self._client.decr(key))
                if current <= 0:
                    self._client.delete(key)
                    return
                return
            except Exception:
                self._enter_degraded("release_inflight")
        with self._local_lock:
            current = int(self._local_inflight.get(scope, 0))
            if current <= 1:
                self._local_inflight.pop(scope, None)
            else:
                self._local_inflight[scope] = current - 1

    # ----------------------------------------------------------- idempotency
    def claim_idempotency(self, tenant_id: str, idem_key: str) -> bool:
        ttl = int(os.getenv("TRAVEL_IDEMPOTENCY_TTL_SEC", "900"))
        key = f"{_IDEMPOTENCY_KEY_PREFIX}{{tenant:{tenant_id}}}:{idem_key}"
        if self._client is not None:
            try:
                created = self._client.set(key, str(int(time.time())), ex=ttl, nx=True)
                return bool(created)
            except Exception:
                self._enter_degraded("claim_idempotency")
        if self._degraded and self._fail_closed():
            # Redis was configured but is now erroring: degraded local storage
            # cannot guarantee at-most-once across processes - deny rather than
            # risk duplicate bookings/charges downstream.
            return False
        now = time.time()
        with self._local_lock:
            for stale_key in [k for k, ts in self._local_idempotency.items() if ts <= now]:
                self._local_idempotency.pop(stale_key, None)
            if key in self._local_idempotency:
                return False
            self._local_idempotency[key] = now + ttl
            return True

    # --------------------------------------------------------------- circuit
    def allow_circuit(self, circuit_name: str) -> bool:
        if self._client is not None:
            state = self._redis_circuit_state(circuit_name)
            if state is not None:
                return self._circuit_admit(state, circuit_name)
        return self._local_circuit_admit(circuit_name)

    def _redis_circuit_state(self, circuit_name: str) -> Optional[Dict[str, float]]:
        base = f"{_CIRCUIT_KEY_PREFIX}{circuit_name}"
        try:
            failures = self._client.get(f"{base}:failures")
            open_until = self._client.get(f"{base}:open_until")
            probes = self._client.get(f"{base}:half_open_probes")
            return {
                "failures": float(failures) if failures else 0.0,
                "open_until": float(open_until) if open_until else 0.0,
                "half_open_probes": float(probes) if probes else 0.0,
            }
        except Exception:
            self._enter_degraded("allow_circuit")
            return None

    def _circuit_admit(self, state: Dict[str, float], circuit_name: str) -> bool:
        now = time.time()
        if state["open_until"] > now:
            return False
        if state["open_until"] <= 0.0:
            return True
        # Cooldown elapsed: half-open, admit only a bounded number of probes.
        probes = int(os.getenv("TRAVEL_CIRCUIT_HALF_OPEN_PROBES", "1"))
        key = f"{_CIRCUIT_KEY_PREFIX}{circuit_name}:half_open_probes"
        try:
            current = int(self._client.incr(key))
            self._client.expire(key, max(1, int(os.getenv("TRAVEL_CIRCUIT_COOLDOWN_SEC", "30"))))
            return current <= probes
        except Exception:
            self._enter_degraded("allow_circuit")
            return True

    def _local_circuit_admit(self, circuit_name: str) -> bool:
        now = time.time()
        with self._local_lock:
            state = self._local_circuits.setdefault(circuit_name, {})
            open_until = float(state.get("open_until", 0.0))
            if open_until > now:
                return False
            if open_until <= 0.0:
                return True
            probes = int(os.getenv("TRAVEL_CIRCUIT_HALF_OPEN_PROBES", "1"))
            used = int(state.get("half_open_probes", 0))
            if used >= probes:
                return False
            state["half_open_probes"] = used + 1
            state["half_open_started"] = now
            return True

    def record_success(self, circuit_name: str) -> None:
        if self._client is not None:
            base = f"{_CIRCUIT_KEY_PREFIX}{circuit_name}"
            try:
                for suffix in (":failures", ":open_until", ":half_open_probes"):
                    self._client.delete(f"{base}{suffix}")
                return
            except Exception:
                self._enter_degraded("record_success")
        with self._local_lock:
            self._local_circuits.pop(circuit_name, None)

    def record_failure(self, circuit_name: str) -> None:
        threshold = int(os.getenv("TRAVEL_CIRCUIT_FAIL_THRESHOLD", "5"))
        cooldown = int(os.getenv("TRAVEL_CIRCUIT_COOLDOWN_SEC", "30"))
        if self._client is not None:
            fail_key = f"{_CIRCUIT_KEY_PREFIX}{circuit_name}:failures"
            open_key = f"{_CIRCUIT_KEY_PREFIX}{circuit_name}:open_until"
            try:
                failures = int(self._client.incr(fail_key))
                self._client.expire(fail_key, cooldown)
                if failures >= threshold:
                    self._client.setex(open_key, cooldown, str(time.time() + cooldown))
                    self._client.delete(f"{_CIRCUIT_KEY_PREFIX}{circuit_name}:half_open_probes")
                return
            except Exception:
                self._enter_degraded("record_failure")
        with self._local_lock:
            state = self._local_circuits.setdefault(circuit_name, {})
            state["failures"] = int(state.get("failures", 0)) + 1
            state["failures_at"] = time.time()
            if int(state["failures"]) >= threshold:
                state["open_until"] = time.time() + cooldown
                state["half_open_probes"] = 0

    # ------------------------------------------------------------- degraded
    def _enter_degraded(self, operation: str) -> None:
        if not self._degraded:
            self._degraded = True
            logger.warning(
                "traffic guard degraded to local limits during %s "
                "(redis unavailable); set TRAVEL_GUARD_FAIL_CLOSED=true to deny "
                "idempotency claims while degraded",
                operation,
            )
