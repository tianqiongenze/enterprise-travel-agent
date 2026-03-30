"""Module provides service components and helpers."""

import unittest
from unittest.mock import patch

from src.travel_agent.a2a.router import A2ARouter


class _FakeRedisClient:
    def __init__(self) -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.pending: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.seq = 0

    def xgroup_create(self, key: str, group: str, id: str = "0", mkstream: bool = True) -> bool:
        _ = (group, id, mkstream)
        self.streams.setdefault(key, [])
        self.pending.setdefault(key, [])
        return True

    def xadd(self, key: str, fields: dict[str, str], maxlen: int = 1000, approximate: bool = True) -> str:
        _ = approximate
        self.seq += 1
        entry_id = f"{self.seq}-0"
        self.streams.setdefault(key, []).append((entry_id, fields))
        if len(self.streams[key]) > maxlen:
            self.streams[key] = self.streams[key][-maxlen:]
        return entry_id

    def xreadgroup(self, groupname: str, consumername: str, streams: dict[str, str], count: int = 10, block: int = 0):
        _ = (groupname, consumername, block)
        key = next(iter(streams.keys()))
        rows = self.streams.get(key, [])[:count]
        self.streams[key] = self.streams.get(key, [])[count:]
        self.pending.setdefault(key, []).extend(rows)
        return [(key, rows)]

    def xautoclaim(self, key: str, group: str, consumer: str, min_idle_time: int, start_id: str, count: int = 10):
        _ = (group, consumer, min_idle_time, start_id)
        rows = self.pending.get(key, [])[:count]
        self.pending[key] = self.pending.get(key, [])[count:]
        return ("0-0", rows)

    def xack(self, key: str, group: str, entry_id: str) -> int:
        _ = (key, group, entry_id)
        return 1

    def pipeline(self, transaction: bool = False):
        _ = transaction
        client = self

        class _Pipe:
            def __init__(self) -> None:
                self.ops: list[tuple[str, str, str]] = []

            def xack(self, key: str, group: str, entry_id: str) -> None:
                self.ops.append((key, group, entry_id))

            def execute(self) -> None:
                for key, group, entry_id in self.ops:
                    client.xack(key, group, entry_id)

        return _Pipe()


class _FakeRedisModule:
    _client = _FakeRedisClient()

    class Redis:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = (url, decode_responses)
            return _FakeRedisModule._client


class _ImportGuard:
    def __init__(self, fallback):
        self.fallback = fallback

    def __call__(self, name: str):
        if name == "redis":
            return _FakeRedisModule
        if name == "pulsar":
            raise ImportError("pulsar not installed")
        return self.fallback(name)


class A2ARedisStreamsTestCase(unittest.TestCase):
    def test_publish_and_consume_via_streams(self) -> None:
        import importlib as raw_importlib

        with patch("importlib.import_module", side_effect=_ImportGuard(raw_importlib.import_module)):
            router = A2ARouter()
            sent = router.send("manager-agent", "trip-planner-agent", "route", {"city": "上海"})
            self.assertEqual(sent.receiver, "trip-planner-agent")
            inbox = router.inbox("trip-planner-agent")
            self.assertTrue(len(inbox) >= 1)
            self.assertEqual(inbox[0].get("topic"), "route")


if __name__ == "__main__":
    unittest.main()

