"""Module provides service components and helpers."""

import os
import tempfile
import unittest

from src.travel_agent.events.consumer import ConsumerMetrics, EventHandler, EventMessage, RetryPolicy, process_local_events


class _AlwaysFailHandler(EventHandler):
    topic = "recommend."

    def handle(self, message: EventMessage) -> None:
        raise RuntimeError(f"boom:{message.topic}")


class EventConsumerPipelineTestCase(unittest.TestCase):
    def test_local_pipeline_writes_audit_profile_notification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous = os.environ.get("TRAVEL_EVENT_OUT_DIR")
            os.environ["TRAVEL_EVENT_OUT_DIR"] = temp_dir

            events = [
                {
                    "topic": "recommend.requested",
                    "payload": {"city": "上海", "days": 3},
                },
                {
                    "topic": "recommend.completed",
                    "payload": {"city": "上海", "hotel_count": 3, "transport_count": 2, "itinerary_days": 3},
                },
                {
                    "topic": "a2a.route_plan",
                    "payload": {"sender": "manager-agent", "receiver": "route-making-agent"},
                },
            ]
            count = process_local_events(events)
            self.assertEqual(count, 3)

            self.assertTrue(os.path.exists(os.path.join(temp_dir, "audit_events.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "profile_updates.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "notifications.jsonl")))
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "a2a_audit_events.jsonl")))

            if previous is None:
                del os.environ["TRAVEL_EVENT_OUT_DIR"]
            else:
                os.environ["TRAVEL_EVENT_OUT_DIR"] = previous

    def test_retry_and_dlq_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous = os.environ.get("TRAVEL_EVENT_OUT_DIR")
            os.environ["TRAVEL_EVENT_OUT_DIR"] = temp_dir

            policy = RetryPolicy(max_retries=2, backoff_ms=1, enable_dlq=True)
            metrics = ConsumerMetrics()
            events = [{"topic": "recommend.completed", "payload": {"city": "北京"}}]

            processed = process_local_events(events, handlers=[_AlwaysFailHandler()], retry_policy=policy, metrics=metrics)
            self.assertEqual(processed, 0)
            self.assertEqual(metrics.received_total, 1)
            self.assertEqual(metrics.processed_total, 0)
            self.assertEqual(metrics.retried_total, 2)
            self.assertEqual(metrics.dlq_total, 1)
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "local_dlq_events.jsonl")))

            if previous is None:
                del os.environ["TRAVEL_EVENT_OUT_DIR"]
            else:
                os.environ["TRAVEL_EVENT_OUT_DIR"] = previous


if __name__ == "__main__":
    unittest.main()

