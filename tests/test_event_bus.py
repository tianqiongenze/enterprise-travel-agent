"""Module provides service components and helpers."""

import os
import unittest
from unittest.mock import patch

from src.travel_agent.events.bus import LocalEventBus, build_event_bus_from_env


class EventBusTestCase(unittest.TestCase):
    def _set_env(self, key: str, value: str):
        previous = os.environ.get(key)
        os.environ[key] = value
        return previous

    def _restore_env(self, key: str, previous):
        if previous is None:
            del os.environ[key]
        else:
            os.environ[key] = previous

    def test_default_pulsar_falls_back_to_local_when_dependency_missing(self) -> None:
        previous_backend = self._set_env("TRAVEL_EVENT_BUS", "pulsar")
        previous_strict = self._set_env("TRAVEL_EVENT_BUS_STRICT", "false")
        try:
            with patch("src.travel_agent.events.bus.PulsarEventBus", side_effect=Exception("pulsar unavailable")):
                bus = build_event_bus_from_env()
            bus.publish("unit.test", {"ok": True})
            self.assertIsInstance(bus, LocalEventBus)
        finally:
            self._restore_env("TRAVEL_EVENT_BUS", previous_backend)
            self._restore_env("TRAVEL_EVENT_BUS_STRICT", previous_strict)

    def test_pulsar_strict_mode_raises_on_missing_dependency(self) -> None:
        previous_backend = self._set_env("TRAVEL_EVENT_BUS", "pulsar")
        previous_strict = self._set_env("TRAVEL_EVENT_BUS_STRICT", "true")
        try:
            with patch("src.travel_agent.events.bus.PulsarEventBus", side_effect=Exception("pulsar unavailable")):
                with self.assertRaises(RuntimeError):
                    build_event_bus_from_env()
        finally:
            self._restore_env("TRAVEL_EVENT_BUS", previous_backend)
            self._restore_env("TRAVEL_EVENT_BUS_STRICT", previous_strict)

    def test_local_bus_keeps_events_for_debug(self) -> None:
        bus = LocalEventBus()
        bus.publish("recommend.requested", {"city": "北京"})
        self.assertEqual(len(bus.events), 1)
        self.assertEqual(bus.events[0]["topic"], "recommend.requested")


if __name__ == "__main__":
    unittest.main()
