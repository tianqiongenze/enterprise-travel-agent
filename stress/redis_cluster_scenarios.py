"""Module provides service components and helpers."""

import asyncio
import json

from src.travel_agent.cache.redis_manager import cache_manager


async def run() -> None:
    print("[redis-scenarios] start")

    await cache_manager.set_hot_destination_plan("北京", {"theme": "family", "days": 3})
    hot = await cache_manager.get_hot_destination_plan("北京")
    print("hot_plan:", json.dumps(hot, ensure_ascii=False))

    limited_before = await cache_manager.is_rate_limited("user-demo", limit=2, window_sec=60)
    limited_after_1 = await cache_manager.is_rate_limited("user-demo", limit=2, window_sec=60)
    limited_after_2 = await cache_manager.is_rate_limited("user-demo", limit=2, window_sec=60)
    print("rate_limit:", limited_before, limited_after_1, limited_after_2)

    await cache_manager.set_user_profile_cache("tenant-demo", "user-demo", {"tier": "gold", "city": "北京"})
    profile = await cache_manager.get_user_profile_cache("tenant-demo", "user-demo")
    print("profile:", json.dumps(profile, ensure_ascii=False))

    replay_1 = await cache_manager.is_idempotency_replayed("tenant-demo", "idem-001", ttl=300)
    replay_2 = await cache_manager.is_idempotency_replayed("tenant-demo", "idem-001", ttl=300)
    print("idempotency_replay:", replay_1, replay_2)

    locked = await cache_manager.try_distributed_lock("deploy-window", "owner-a", ttl_sec=20)
    released = await cache_manager.release_distributed_lock("deploy-window", "owner-a")
    print("lock:", locked, released)

    await cache_manager.set_itinerary_snapshot(
        "tenant-demo",
        "user-demo",
        "conv-001",
        {"city": "北京", "days": 3, "theme": "family"},
    )
    snapshot = await cache_manager.get_itinerary_snapshot("tenant-demo", "user-demo", "conv-001")
    print("itinerary_snapshot:", json.dumps(snapshot, ensure_ascii=False))

    popularity_1 = await cache_manager.incr_city_popularity("北京")
    popularity_2 = await cache_manager.incr_city_popularity("北京")
    popularity_now = await cache_manager.get_city_popularity("北京")
    print("city_popularity:", popularity_1, popularity_2, popularity_now)

    await cache_manager.push_recent_search("tenant-demo", "user-demo", {"city": "北京", "days": 3})
    await cache_manager.push_recent_search("tenant-demo", "user-demo", {"city": "上海", "days": 2})
    recent = await cache_manager.get_recent_searches("tenant-demo", "user-demo", limit=5)
    print("recent_searches:", json.dumps(recent, ensure_ascii=False))

    print("[redis-scenarios] done")


if __name__ == "__main__":
    asyncio.run(run())

