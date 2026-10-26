"""TDD tests for the multi-level cache (fourth-round R3, plan §四.R3)."""

from __future__ import annotations

import asyncio

import pytest

from src.travel_agent.cache.multilevel import (
    MultiLevelCache,
    _SimpleTTLCache,
    _default_deserialize,
    _default_serialize,
)


class _FakeRedis:
    """Minimal async redis double: get/setex/delete/publish + pubsub stub."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.published: list[tuple[str, str]] = []
        self.fail = False

    async def get(self, key):
        if self.fail:
            raise RuntimeError("redis down")
        return self.store.get(key)

    def pipeline(self, transaction=False):
        return _FakePipeline(self)

    def pubsub(self):
        return _FakePubSub()


class _FakePipeline:
    def __init__(self, client: _FakeRedis) -> None:
        self._client = client
        self._ops = []

    def delete(self, key):
        self._ops.append(("delete", key))

    def publish(self, channel, body):
        self._ops.append(("publish", channel, body))

    async def execute(self):
        for op in self._ops:
            if op[0] == "delete":
                self._client.store.pop(op[1], None)
            else:
                self._client.published.append((op[1], op[2]))


class _FakePubSub:
    async def subscribe(self, channel):
        pass

    async def listen(self):
        await asyncio.sleep(3600)
        yield {}


@pytest.mark.asyncio
async def test_l1_hit_then_loader_not_called_twice():
    calls = []

    async def loader():
        calls.append(1)
        return {"v": 42}

    cache = MultiLevelCache(redis_client=None)
    first = await cache.get_or_load("k", loader, ttl_seconds=30)
    second = await cache.get_or_load("k", loader, ttl_seconds=30)
    assert first == second == {"v": 42}
    assert len(calls) == 1, "L1 must absorb the second read"
    assert cache.counters["l1_hit"] == 1


@pytest.mark.asyncio
async def test_l2_backfills_l1_and_records_hits():
    redis = _FakeRedis()
    redis.store["k"] = _default_serialize({"v": 7})
    cache = MultiLevelCache(redis_client=redis)

    async def loader():  # pragma: no cover - must not be reached
        raise AssertionError("loader must not run on L2 hit")

    value = await cache.get_or_load("k", loader, ttl_seconds=30)
    assert value == {"v": 7}
    assert cache.counters["l2_hit"] == 1
    # second read served by L1
    await cache.get_or_load("k", loader, ttl_seconds=30)
    assert cache.counters["l1_hit"] == 1


@pytest.mark.asyncio
async def test_redis_outage_is_fail_open():
    redis = _FakeRedis()
    redis.fail = True
    cache = MultiLevelCache(redis_client=redis)

    async def loader():
        return "origin"

    assert await cache.get_or_load("k", loader) == "origin"
    assert cache.counters["miss"] == 1


@pytest.mark.asyncio
async def test_invalidate_drops_l1_l2_and_broadcasts():
    redis = _FakeRedis()
    cache = MultiLevelCache(redis_client=redis)

    async def loader():
        return 1

    await cache.get_or_load("k", loader, ttl_seconds=60)
    assert cache.counters["l1_hit"] >= 0
    await cache.invalidate("k")
    assert cache._l1.get("k") is None, "L1 entry must be dropped"
    assert "k" not in redis.store, "L2 entry must be deleted"
    assert redis.published, "invalidation must be broadcast"


@pytest.mark.asyncio
async def test_hit_rate_metric_shape():
    cache = MultiLevelCache(redis_client=None)

    async def loader():
        return 1

    await cache.get_or_load("k", loader)
    await cache.get_or_load("k", loader)
    metrics = cache.prometheus_metrics()
    assert "travel_cache_hit_rate" in metrics
    assert "travel_cache_l1_hits_total 1" in metrics


@pytest.mark.asyncio
async def test_loader_failure_propagates():
    cache = MultiLevelCache(redis_client=None)

    async def loader():
        raise ValueError("origin down")

    with pytest.raises(ValueError):
        await cache.get_or_load("k", loader)


def test_simple_ttl_cache_expiry():
    import time

    c = _SimpleTTLCache(maxsize=4, ttl=0.05)
    c.set("a", 1)
    assert c.get("a") == 1
    time.sleep(0.08)
    assert c.get("a") is None
