"""Module provides service components and helpers."""

import unittest

from src.travel_agent.access.control import enforce_tools_for_tier, get_tier_policy


class AccessControlTestCase(unittest.TestCase):
    def test_basic_tier_filters_tools(self) -> None:
        tools = enforce_tools_for_tier("basic", ["search_hotels", "search_events", "search_transports"])
        self.assertEqual(tools, ["search_hotels", "search_transports"])

    def test_gold_tier_allows_event_tools(self) -> None:
        tools = enforce_tools_for_tier("gold", ["search_hotels", "search_events"])
        self.assertEqual(tools, ["search_hotels", "search_events"])

    def test_unknown_tier_falls_back_basic(self) -> None:
        policy = get_tier_policy("unknown")
        self.assertEqual(policy.name, "basic")


if __name__ == "__main__":
    unittest.main()

