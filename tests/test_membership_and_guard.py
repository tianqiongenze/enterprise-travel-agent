"""Module provides service components and helpers."""

import os
import unittest

from src.travel_agent.membership_store import MembershipStore
from src.travel_agent.traffic_guard import TrafficGuard


class _FakeGuardRedis:
    def __init__(self) -> None:
        self.values = {}

    def register_script(self, lua):
        # Token-bucket path (fourth-round R4): emulate the Lua script's
        # contract in Python so the fixed-window assertions keep working.
        client = self

        class _Script:
            def __call__(self, keys, args):
                import math

                key = keys[0]
                capacity, refill, now, requested = (float(a) for a in args)
                st = client.values.get(key)
                if st is None:
                    tokens, ts = capacity, now
                else:
                    tokens, ts = st
                elapsed = max(0.0, now - ts)
                tokens = min(capacity, tokens + elapsed * refill)
                allowed = 1 if tokens >= requested else 0
                if allowed:
                    tokens -= requested
                client.values[key] = (tokens, now)
                return allowed

        return _Script()

    def incr(self, key: str) -> int:
        value = int(self.values.get(key, 0)) + 1
        self.values[key] = value
        return value

    def expire(self, key: str, seconds: int) -> bool:
        _ = (key, seconds)
        return True

    def set(self, key: str, value: str, ex: int = 0, nx: bool = False):
        _ = ex
        if nx and key in self.values:
            return None
        self.values[key] = value
        return True

    def get(self, key: str):
        return self.values.get(key)

    def delete(self, key: str) -> int:
        if key in self.values:
            del self.values[key]
            return 1
        return 0

    def setex(self, key: str, seconds: int, value: str) -> bool:
        _ = seconds
        self.values[key] = value
        return True


class MembershipAndGuardTestCase(unittest.TestCase):
    def test_membership_store_memory_roundtrip(self) -> None:
        store = MembershipStore()
        store._client = None
        store.set_tier("tenant-1", "user-1", "gold")
        tier = store.get_tier("tenant-1", "user-1")
        self.assertEqual(tier, "gold")

    def test_traffic_guard_limit_and_idempotency(self) -> None:
        guard = TrafficGuard()
        guard._client = _FakeGuardRedis()

        self.assertTrue(guard.allow_request("tenant-1:user-1:ip"))
        self.assertTrue(guard.claim_idempotency("tenant-1", "idem-1"))
        self.assertFalse(guard.claim_idempotency("tenant-1", "idem-1"))

    def test_traffic_guard_rate_limit_from_env(self) -> None:
        old_limit = os.environ.get("TRAVEL_RATE_LIMIT_PER_MINUTE")
        old_window = os.environ.get("TRAVEL_RATE_LIMIT_WINDOW_SEC")
        os.environ["TRAVEL_RATE_LIMIT_PER_MINUTE"] = "2"
        os.environ["TRAVEL_RATE_LIMIT_WINDOW_SEC"] = "30"
        # Token bucket (R4): capacity = limit × burst(1.5) = 3, so the third
        # request is still inside the burst; the fourth must be rejected.
        os.environ["TRAVEL_RATE_BURST"] = "1.0"
        try:
            guard = TrafficGuard()
            guard._client = _FakeGuardRedis()
            scope = "tenant-2:user-7:ip"
            self.assertTrue(guard.allow_request(scope))
            self.assertTrue(guard.allow_request(scope))
            self.assertFalse(guard.allow_request(scope))
        finally:
            if old_limit is None:
                del os.environ["TRAVEL_RATE_LIMIT_PER_MINUTE"]
            else:
                os.environ["TRAVEL_RATE_LIMIT_PER_MINUTE"] = old_limit
            if old_window is None:
                del os.environ["TRAVEL_RATE_LIMIT_WINDOW_SEC"]
            else:
                os.environ["TRAVEL_RATE_LIMIT_WINDOW_SEC"] = old_window
            if "TRAVEL_RATE_BURST" in os.environ:
                del os.environ["TRAVEL_RATE_BURST"]

    def test_traffic_guard_circuit_breaker(self) -> None:
        old_threshold = os.environ.get("TRAVEL_CIRCUIT_FAIL_THRESHOLD")
        old_cooldown = os.environ.get("TRAVEL_CIRCUIT_COOLDOWN_SEC")
        os.environ["TRAVEL_CIRCUIT_FAIL_THRESHOLD"] = "3"
        os.environ["TRAVEL_CIRCUIT_COOLDOWN_SEC"] = "60"
        try:
            guard = TrafficGuard()
            guard._client = _FakeGuardRedis()

            for _ in range(3):
                guard.record_failure("runtime_recommend")
            self.assertFalse(guard.allow_circuit("runtime_recommend"))
            guard.record_success("runtime_recommend")
            self.assertTrue(guard.allow_circuit("runtime_recommend"))
        finally:
            if old_threshold is None:
                del os.environ["TRAVEL_CIRCUIT_FAIL_THRESHOLD"]
            else:
                os.environ["TRAVEL_CIRCUIT_FAIL_THRESHOLD"] = old_threshold
            if old_cooldown is None:
                del os.environ["TRAVEL_CIRCUIT_COOLDOWN_SEC"]
            else:
                os.environ["TRAVEL_CIRCUIT_COOLDOWN_SEC"] = old_cooldown


if __name__ == "__main__":
    unittest.main()
