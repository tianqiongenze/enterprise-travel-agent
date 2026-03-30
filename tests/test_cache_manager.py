"""Module provides service components and helpers."""

import unittest
from typing import Dict, List, Optional

from src.travel_agent.cache.redis_manager import CacheManager


class FakeAsyncRedis:
    def __init__(self) -> None:
        self.values: Dict[str, str] = {}
        self.lists: Dict[str, List[str]] = {}

    async def get(self, key: str) -> Optional[str]:
        return self.values.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        _ = ttl
        self.values[key] = value
        return True

    async def set(self, key: str, value: str, ex: Optional[int] = None, nx: bool = False) -> Optional[bool]:
        _ = ex
        if nx and key in self.values:
            return None
        self.values[key] = value
        return True

    async def incr(self, key: str) -> int:
        current = int(self.values.get(key, "0"))
        current += 1
        self.values[key] = str(current)
        return current

    async def expire(self, key: str, ttl: int) -> bool:
        _ = (key, ttl)
        return True

    async def delete(self, key: str) -> int:
        if key in self.values:
            del self.values[key]
            return 1
        return 0

    async def lpush(self, key: str, value: str) -> int:
        rows = self.lists.setdefault(key, [])
        rows.insert(0, value)
        return len(rows)

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        rows = self.lists.get(key, [])
        self.lists[key] = rows[start : end + 1]
        return True

    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        rows = self.lists.get(key, [])
        return rows[start : end + 1]


class CacheManagerTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.manager = CacheManager()
        self.manager.redis_client = FakeAsyncRedis()

    async def test_itinerary_snapshot_roundtrip(self) -> None:
        await self.manager.set_itinerary_snapshot("tenant-a", "user-1", "conv-1", {"city": "北京", "days": 2})
        snapshot = await self.manager.get_itinerary_snapshot("tenant-a", "user-1", "conv-1")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.get("city"), "北京")

    async def test_city_popularity_counter(self) -> None:
        first = await self.manager.incr_city_popularity("上海")
        second = await self.manager.incr_city_popularity("上海")
        total = await self.manager.get_city_popularity("上海")
        self.assertEqual(first, 1)
        self.assertEqual(second, 2)
        self.assertEqual(total, 2)

    async def test_recent_searches(self) -> None:
        await self.manager.push_recent_search("tenant-a", "user-1", {"city": "北京", "days": 3})
        await self.manager.push_recent_search("tenant-a", "user-1", {"city": "成都", "days": 4})
        rows = await self.manager.get_recent_searches("tenant-a", "user-1", limit=2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].get("city"), "成都")


if __name__ == "__main__":
    unittest.main()

