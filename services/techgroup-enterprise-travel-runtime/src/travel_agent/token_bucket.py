"""Token-bucket rate limiting (fourth-round R4, plan §四.R4).

Replaces the fixed-window counter in TrafficGuard with a token bucket:

- capacity  ``TRAVEL_RATE_BURST``        (default 1.5× per-minute limit)
- refill    ``limit / window`` tokens/s  (continuous, not window-aligned)
- Redis     single Lua script — atomic check-and-consume (no INCR/EXPIRE
            race, no window boundary burst)
- fallback  in-process sliding deque (same semantics, per-pod scope)

Redis 8 hash-field-TTL would let us keep per-bucket state in one hash, but
the Lua path is equivalent and works on any Redis ≥2.6 the cluster runs.
"""

from __future__ import annotations

import math
import os
import time

# KEYS[1] = bucket key
# ARGV: capacity, refill_per_sec, now_seconds, requested
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local state = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(state[1])
local ts = tonumber(state[2])
if tokens == nil then
    tokens = capacity
    ts = now
end

local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * refill)

local allowed = 0
if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
end

redis.call('HSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, math.ceil(capacity / refill) + 60)
return allowed
"""


def token_bucket_env() -> tuple[int, float]:
    """(capacity, refill_per_sec) from env; refill derives from the
    existing per-minute limit so defaults stay compatible."""
    limit = int(os.getenv("TRAVEL_RATE_LIMIT_PER_MINUTE", "200"))
    window = int(os.getenv("TRAVEL_RATE_LIMIT_WINDOW_SEC", "60"))
    refill = limit / max(1, window)
    burst = float(os.getenv("TRAVEL_RATE_BURST", "1.5"))
    capacity = max(1.0, limit * burst)
    return int(capacity), refill


class TokenBucket:
    """In-process token bucket (fallback when Redis is unavailable)."""

    def __init__(self, capacity: int, refill_per_sec: float) -> None:
        self.capacity = float(capacity)
        self.refill = refill_per_sec
        self.tokens = float(capacity)
        self.ts = time.monotonic()

    def allow(self, requested: float = 1.0) -> bool:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.ts) * self.refill)
        self.ts = now
        if self.tokens >= requested:
            self.tokens -= requested
            return True
        return False


def redis_allow(client, key: str, capacity: int, refill: float, requested: float = 1.0) -> bool | None:
    """Atomic token-bucket consume via Lua. Returns None on Redis failure."""
    try:
        script = client.register_script(_TOKEN_BUCKET_LUA)
        result = script(
            keys=[key],
            args=[capacity, refill, time.time(), requested],
        )
        return int(result) == 1
    except Exception:
        return None
