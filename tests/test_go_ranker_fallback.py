"""Module provides service components and helpers."""

import os
import unittest

from src.travel_agent.recommendation.go_ranker_client import GoRankerClient


class GoRankerFallbackTestCase(unittest.TestCase):
    def test_default_backend_returns_none(self) -> None:
        previous = os.environ.get("TRAVEL_RANKER_BACKEND")
        if "TRAVEL_RANKER_BACKEND" in os.environ:
            del os.environ["TRAVEL_RANKER_BACKEND"]
        client = GoRankerClient()
        result = client.score_hotel(800, 4.5, ["comfort"], 3000, {"comfort": 1.2})
        self.assertIsNone(result)
        if previous is not None:
            os.environ["TRAVEL_RANKER_BACKEND"] = previous

    def test_go_backend_failure_falls_back_none(self) -> None:
        previous_backend = os.environ.get("TRAVEL_RANKER_BACKEND")
        previous_url = os.environ.get("TRAVEL_GO_RANKER_URL")
        os.environ["TRAVEL_RANKER_BACKEND"] = "go"
        os.environ["TRAVEL_GO_RANKER_URL"] = "http://127.0.0.1:65530"
        client = GoRankerClient()
        result = client.score_transport(600, 2.0, ["fast"], 1000, {"fast": 1.0})
        self.assertIsNone(result)
        if previous_backend is None:
            del os.environ["TRAVEL_RANKER_BACKEND"]
        else:
            os.environ["TRAVEL_RANKER_BACKEND"] = previous_backend
        if previous_url is None:
            del os.environ["TRAVEL_GO_RANKER_URL"]
        else:
            os.environ["TRAVEL_GO_RANKER_URL"] = previous_url


if __name__ == "__main__":
    unittest.main()
