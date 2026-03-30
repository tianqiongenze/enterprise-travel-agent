"""Module provides service components and helpers."""

import os
import unittest

from src.travel_agent.memory.redis_store import RedisMemoryStore


class RedisClusterModeTestCase(unittest.TestCase):
    def test_redis_store_accepts_cluster_mode_config(self) -> None:
        prev_url = os.environ.get("TRAVEL_REDIS_URL")
        prev_mode = os.environ.get("TRAVEL_REDIS_MODE")

        os.environ["TRAVEL_REDIS_URL"] = "redis://127.0.0.1:7000"
        os.environ["TRAVEL_REDIS_MODE"] = "cluster"

        store = RedisMemoryStore()
        # init should not raise, even if runtime server is unavailable in unit environment.
        self.assertTrue(hasattr(store, "enabled"))

        if prev_url is None:
            del os.environ["TRAVEL_REDIS_URL"]
        else:
            os.environ["TRAVEL_REDIS_URL"] = prev_url
        if prev_mode is None:
            del os.environ["TRAVEL_REDIS_MODE"]
        else:
            os.environ["TRAVEL_REDIS_MODE"] = prev_mode


if __name__ == "__main__":
    unittest.main()

