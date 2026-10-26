"""TDD tests for token-bucket rate limiting (fourth-round R4)."""

from __future__ import annotations

import time

import pytest

from src.travel_agent.token_bucket import TokenBucket, token_bucket_env


def test_token_bucket_burst_then_throttle():
    bucket = TokenBucket(capacity=5, refill_per_sec=0.0)  # no refill: pure burst
    results = [bucket.allow() for _ in range(8)]
    assert results == [True] * 5 + [False] * 3


def test_token_bucket_refills_continuously():
    bucket = TokenBucket(capacity=2, refill_per_sec=10.0)
    assert bucket.allow() and bucket.allow() and not bucket.allow()
    time.sleep(0.15)  # ~1.5 tokens refilled
    assert bucket.allow()


def test_env_defaults_keep_per_minute_semantics(monkeypatch):
    monkeypatch.setenv("TRAVEL_RATE_LIMIT_PER_MINUTE", "200")
    monkeypatch.delenv("TRAVEL_RATE_BURST", raising=False)
    capacity, refill = token_bucket_env()
    assert capacity == 300  # 200 × 1.5 burst
    assert abs(refill - 200 / 60) < 1e-9


@pytest.mark.asyncio
async def test_traffic_guard_allow_request_uses_token_bucket(monkeypatch):
    from src.travel_agent.traffic_guard import TrafficGuard

    guard = TrafficGuard()
    monkeypatch.setattr(guard, "_client", None)
    # Drain the burst (default 300) then expect rejections.
    granted = sum(1 for _ in range(400) if guard.allow_request("tb-test"))
    assert granted <= 300, "burst capacity must bound the grant count"
    assert granted >= 100, "sane configuration must grant the initial burst"


class _FakeLuaRedis:
    """Redis double that actually interprets our Lua logic in Python."""

    def __init__(self) -> None:
        self.state: dict[str, dict] = {}

    def register_script(self, lua):  # noqa: ARG002
        client = self

        class _Script:
            def __call__(self, keys, args):
                import math

                key = keys[0]
                capacity, refill, now, requested = (float(a) for a in args)
                st = client.state.get(key, {"tokens": capacity, "ts": now})
                tokens = st["tokens"]
                elapsed = max(0.0, now - st["ts"])
                tokens = min(capacity, tokens + elapsed * refill)
                allowed = 0
                if tokens >= requested:
                    tokens -= requested
                    allowed = 1
                client.state[key] = {"tokens": tokens, "ts": now}
                return allowed

        return _Script()


@pytest.mark.asyncio
async def test_redis_token_bucket_atomic_contract(monkeypatch):
    from src.travel_agent.token_bucket import redis_allow

    client = _FakeLuaRedis()
    # capacity 3, no refill: first 3 allowed then denied — atomically
    assert redis_allow(client, "k", capacity=3, refill=0.0) is True
    assert redis_allow(client, "k", capacity=3, refill=0.0) is True
    assert redis_allow(client, "k", capacity=3, refill=0.0) is True
    assert redis_allow(client, "k", capacity=3, refill=0.0) is False


@pytest.mark.asyncio
async def test_redis_failure_returns_none_falls_back(monkeypatch):
    from src.travel_agent.token_bucket import redis_allow

    class _Broken:
        def register_script(self, lua):
            raise RuntimeError("redis down")

    assert redis_allow(_Broken(), "k", capacity=3, refill=0.1) is None
