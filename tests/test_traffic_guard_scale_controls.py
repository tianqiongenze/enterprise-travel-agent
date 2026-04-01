"""Tests for traffic guard scale controls."""

import os
import unittest

from src.travel_agent.traffic_guard import TrafficGuard


class TrafficGuardScaleControlsTestCase(unittest.TestCase):
    def test_local_inflight_limit_blocks_when_exceeded(self) -> None:
        previous = os.environ.get("TRAVEL_LOCAL_INFLIGHT_LIMIT")
        os.environ["TRAVEL_LOCAL_INFLIGHT_LIMIT"] = "1"
        guard = TrafficGuard()
        self.assertTrue(guard.claim_inflight("tenant-a:beijing"))
        self.assertFalse(guard.claim_inflight("tenant-a:beijing"))
        guard.release_inflight("tenant-a:beijing")
        self.assertTrue(guard.claim_inflight("tenant-a:beijing"))
        guard.release_inflight("tenant-a:beijing")
        if previous is None:
            del os.environ["TRAVEL_LOCAL_INFLIGHT_LIMIT"]
        else:
            os.environ["TRAVEL_LOCAL_INFLIGHT_LIMIT"] = previous


if __name__ == "__main__":
    unittest.main()

