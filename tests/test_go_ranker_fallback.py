"""Module provides service components and helpers."""

import os
import unittest
from unittest.mock import patch

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

    def test_grpc_transport_uses_grpc_path(self) -> None:
        previous_backend = os.environ.get("TRAVEL_RANKER_BACKEND")
        previous_transport = os.environ.get("TRAVEL_GO_RANKER_TRANSPORT")
        os.environ["TRAVEL_RANKER_BACKEND"] = "go"
        os.environ["TRAVEL_GO_RANKER_TRANSPORT"] = "grpc"
        client = GoRankerClient()
        with patch.object(client, "_request_score_grpc", return_value=0.91) as grpc_call:
            with patch.object(client, "_request_score_http", return_value=0.55) as http_call:
                result = client.score_hotel(800, 4.5, ["comfort"], 3000, {"comfort": 1.2})
                self.assertEqual(result, 0.91)
                self.assertTrue(grpc_call.called)
                self.assertFalse(http_call.called)
        if previous_backend is None:
            del os.environ["TRAVEL_RANKER_BACKEND"]
        else:
            os.environ["TRAVEL_RANKER_BACKEND"] = previous_backend
        if previous_transport is None:
            del os.environ["TRAVEL_GO_RANKER_TRANSPORT"]
        else:
            os.environ["TRAVEL_GO_RANKER_TRANSPORT"] = previous_transport

    def test_grpc_transport_falls_back_to_http(self) -> None:
        previous_backend = os.environ.get("TRAVEL_RANKER_BACKEND")
        previous_transport = os.environ.get("TRAVEL_GO_RANKER_TRANSPORT")
        previous_fallback = os.environ.get("TRAVEL_GO_RANKER_GRPC_FALLBACK_HTTP")
        os.environ["TRAVEL_RANKER_BACKEND"] = "go"
        os.environ["TRAVEL_GO_RANKER_TRANSPORT"] = "grpc"
        os.environ["TRAVEL_GO_RANKER_GRPC_FALLBACK_HTTP"] = "true"
        client = GoRankerClient()
        with patch.object(client, "_request_score_grpc", return_value=None) as grpc_call:
            with patch.object(client, "_request_score_http", return_value=0.62) as http_call:
                result = client.score_transport(600, 2.0, ["fast"], 1000, {"fast": 1.0})
                self.assertEqual(result, 0.62)
                self.assertTrue(grpc_call.called)
                self.assertTrue(http_call.called)
        if previous_backend is None:
            del os.environ["TRAVEL_RANKER_BACKEND"]
        else:
            os.environ["TRAVEL_RANKER_BACKEND"] = previous_backend
        if previous_transport is None:
            del os.environ["TRAVEL_GO_RANKER_TRANSPORT"]
        else:
            os.environ["TRAVEL_GO_RANKER_TRANSPORT"] = previous_transport
        if previous_fallback is None:
            del os.environ["TRAVEL_GO_RANKER_GRPC_FALLBACK_HTTP"]
        else:
            os.environ["TRAVEL_GO_RANKER_GRPC_FALLBACK_HTTP"] = previous_fallback

    def test_go_backend_batch_http_scores(self) -> None:
        previous_backend = os.environ.get("TRAVEL_RANKER_BACKEND")
        os.environ["TRAVEL_RANKER_BACKEND"] = "go"
        client = GoRankerClient()
        payloads = [
            {"price": 800, "rating": 4.5, "duration": 0.0, "tags": ["comfort"], "budget": 3000, "weights": {"comfort": 1.1}},
            {"price": 900, "rating": 4.2, "duration": 0.0, "tags": ["family"], "budget": 3000, "weights": {"family": 1.0}},
        ]
        with patch.object(client, "_request_batch_http", return_value=[0.88, 0.79]) as batch_call:
            result = client.score_hotel_batch(payloads)
            self.assertEqual(result, [0.88, 0.79])
            self.assertTrue(batch_call.called)
        if previous_backend is None:
            del os.environ["TRAVEL_RANKER_BACKEND"]
        else:
            os.environ["TRAVEL_RANKER_BACKEND"] = previous_backend

    def test_canary_batch_partial_go_returns_sparse(self) -> None:
        previous_backend = os.environ.get("TRAVEL_RANKER_BACKEND")
        previous_percent = os.environ.get("TRAVEL_RANKER_CANARY_PERCENT")
        os.environ["TRAVEL_RANKER_BACKEND"] = "canary"
        os.environ["TRAVEL_RANKER_CANARY_PERCENT"] = "50"
        client = GoRankerClient()
        payloads = [
            {"price": 800, "rating": 4.5, "duration": 0.0, "tags": ["comfort"], "budget": 3000, "weights": {"comfort": 1.1}},
            {"price": 900, "rating": 4.2, "duration": 0.0, "tags": ["family"], "budget": 3000, "weights": {"family": 1.0}},
        ]
        with patch.object(client, "_should_use_go", side_effect=[True, False]):
            with patch.object(client, "_request_batch_http", return_value=[0.91]) as batch_call:
                scores = client.score_hotel_batch(payloads)
                self.assertIsNotNone(scores)
                self.assertEqual(len(scores), 2)
                self.assertEqual(scores, [0.91, None])
                self.assertTrue(batch_call.called)
        if previous_backend is None:
            del os.environ["TRAVEL_RANKER_BACKEND"]
        else:
            os.environ["TRAVEL_RANKER_BACKEND"] = previous_backend
        if previous_percent is None:
            del os.environ["TRAVEL_RANKER_CANARY_PERCENT"]
        else:
            os.environ["TRAVEL_RANKER_CANARY_PERCENT"] = previous_percent


if __name__ == "__main__":
    unittest.main()
