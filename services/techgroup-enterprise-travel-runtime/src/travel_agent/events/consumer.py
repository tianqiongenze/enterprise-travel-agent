"""Module handles event bus interactions."""

import json
import os
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, cast


@dataclass
class EventMessage:
    topic: str
    payload: Dict[str, object]
    ts: str


class EventHandler:
    topic: str

    def handle(self, message: EventMessage) -> None:
        raise NotImplementedError


class _JsonlWriter:
    def __init__(self, filename: str) -> None:
        base = Path(os.getenv("TRAVEL_EVENT_OUT_DIR", "./var/events"))
        base.mkdir(parents=True, exist_ok=True)
        self.file = base / filename

    def write(self, row: Dict[str, object]) -> None:
        with self.file.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")


@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_ms: int = 200
    enable_dlq: bool = True
    dlq_topic: str = "travel-agent.recommend.dlq"


@dataclass
class ConsumerMetrics:
    received_total: int = 0
    processed_total: int = 0
    retried_total: int = 0
    dlq_total: int = 0
    handler_failures_total: int = 0
    last_lag_seconds: float = 0.0
    queue_full_drop_total: int = 0

    def to_prometheus_text(self) -> str:
        lines = [
            f"travel_event_consumer_received_total {self.received_total}",
            f"travel_event_consumer_processed_total {self.processed_total}",
            f"travel_event_consumer_retried_total {self.retried_total}",
            f"travel_event_consumer_dlq_total {self.dlq_total}",
            f"travel_event_consumer_handler_failures_total {self.handler_failures_total}",
            f"travel_event_consumer_lag_seconds {self.last_lag_seconds}",
            f"travel_event_consumer_queue_full_drop_total {self.queue_full_drop_total}",
            f"travel_event_consumer_metrics_timestamp {time.time()}",
        ]
        return "\n".join(lines) + "\n"

    def write_prometheus_file(self, file_path: str) -> None:
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_prometheus_text(), encoding="utf-8")


class AuditEventHandler(EventHandler):
    topic = "recommend."

    def __init__(self) -> None:
        self.writer = _JsonlWriter("audit_events.jsonl")

    def handle(self, message: EventMessage) -> None:
        self.writer.write({
            "ts": message.ts,
            "topic": message.topic,
            "payload": message.payload,
        })


class ProfileEventHandler(EventHandler):
    topic = "recommend.completed"

    def __init__(self) -> None:
        self.writer = _JsonlWriter("profile_updates.jsonl")

    def handle(self, message: EventMessage) -> None:
        city = str(message.payload.get("city", ""))
        self.writer.write({
            "ts": message.ts,
            "city": city,
            "hotel_count": message.payload.get("hotel_count", 0),
            "transport_count": message.payload.get("transport_count", 0),
            "itinerary_days": message.payload.get("itinerary_days", 0),
        })


class NotificationEventHandler(EventHandler):
    topic = "recommend.completed"

    def __init__(self) -> None:
        self.writer = _JsonlWriter("notifications.jsonl")

    def handle(self, message: EventMessage) -> None:
        city = str(message.payload.get("city", ""))
        self.writer.write({
            "ts": message.ts,
            "message": f"Trip recommendation ready for {city}",
        })


class A2AAuditEventHandler(EventHandler):
    topic = "a2a."

    def __init__(self) -> None:
        self.writer = _JsonlWriter("a2a_audit_events.jsonl")

    def handle(self, message: EventMessage) -> None:
        self.writer.write({
            "ts": message.ts,
            "topic": message.topic,
            "payload": message.payload,
        })


def default_handlers() -> List[EventHandler]:
    return [AuditEventHandler(), ProfileEventHandler(), NotificationEventHandler(), A2AAuditEventHandler()]


def dispatch_event(message: EventMessage, handlers: Iterable[EventHandler]) -> None:
    for handler in handlers:
        if message.topic.startswith(handler.topic):
            handler.handle(message)


def _extract_payload(raw: object) -> Dict[str, object]:
    if isinstance(raw, dict):
        return cast(Dict[str, object], raw)
    return {}


def _compute_lag_seconds(ts: str) -> float:
    try:
        published = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0.0, (now - published).total_seconds())
    except Exception:
        return 0.0


def _handle_with_retry(message: EventMessage, handlers: Iterable[EventHandler], policy: RetryPolicy, metrics: ConsumerMetrics) -> None:
    attempts = 0
    while True:
        attempts += 1
        try:
            dispatch_event(message, handlers)
            return
        except Exception:
            metrics.handler_failures_total += 1
            if attempts > policy.max_retries:
                raise
            metrics.retried_total += 1
            time.sleep(max(0, policy.backoff_ms) / 1000.0)


def process_local_events(
    events: List[Dict[str, object]],
    handlers: Optional[List[EventHandler]] = None,
    retry_policy: Optional[RetryPolicy] = None,
    metrics: Optional[ConsumerMetrics] = None,
) -> int:
    active_handlers = handlers or default_handlers()
    policy = retry_policy or RetryPolicy()
    consumer_metrics = metrics or ConsumerMetrics()
    dlq_writer = _JsonlWriter("local_dlq_events.jsonl")
    processed = 0
    now = datetime.now(timezone.utc).isoformat()
    for item in events:
        raw_payload = item.get("payload", {})
        payload = _extract_payload(raw_payload)
        msg = EventMessage(
            topic=str(item.get("topic", "")),
            payload=payload,
            ts=str(item.get("ts", now)),
        )
        consumer_metrics.received_total += 1
        consumer_metrics.last_lag_seconds = _compute_lag_seconds(msg.ts)
        try:
            _handle_with_retry(msg, active_handlers, policy, consumer_metrics)
            processed += 1
            consumer_metrics.processed_total += 1
        except Exception as error:
            if policy.enable_dlq:
                consumer_metrics.dlq_total += 1
                dlq_writer.write({
                    "ts": now,
                    "topic": msg.topic,
                    "payload": msg.payload,
                    "error": str(error),
                })
    return processed


class PulsarConsumerRunner:
    def __init__(self, handlers: Optional[List[EventHandler]] = None) -> None:
        import pulsar  # type: ignore

        self.handlers = handlers or default_handlers()
        service_url = os.getenv("PULSAR_SERVICE_URL", "pulsar://127.0.0.1:6650")
        namespace = os.getenv("PULSAR_NAMESPACE", "public/default")
        prefix = os.getenv("TRAVEL_PULSAR_TOPIC_PREFIX", "travel-agent")
        self.subscription = os.getenv("TRAVEL_PULSAR_SUBSCRIPTION", "travel-agent-consumers")
        self.topic = os.getenv("TRAVEL_PULSAR_CONSUME_TOPIC", f"persistent://{namespace}/{prefix}.recommend.completed")
        self.client = pulsar.Client(service_url)
        self.consumer = self.client.subscribe(self.topic, subscription_name=self.subscription)
        self.retry_policy = RetryPolicy(
            max_retries=int(os.getenv("TRAVEL_EVENT_CONSUMER_MAX_RETRIES", "3")),
            backoff_ms=int(os.getenv("TRAVEL_EVENT_CONSUMER_RETRY_BACKOFF_MS", "200")),
            enable_dlq=os.getenv("TRAVEL_EVENT_CONSUMER_ENABLE_DLQ", "true").strip().lower() == "true",
            dlq_topic=os.getenv("TRAVEL_EVENT_CONSUMER_DLQ_TOPIC", f"persistent://{namespace}/{prefix}.recommend.dlq"),
        )
        self.metrics = ConsumerMetrics()
        self.metrics_path = os.getenv("TRAVEL_EVENT_METRICS_PATH", "stress/pulsar_consumer_metrics.prom")
        self.metrics_flush_every = int(os.getenv("TRAVEL_EVENT_METRICS_FLUSH_EVERY", "10"))
        self.worker_count = int(os.getenv("TRAVEL_EVENT_CONSUMER_WORKERS", "1"))
        self.queue_capacity = int(os.getenv("TRAVEL_EVENT_CONSUMER_QUEUE_CAPACITY", "256"))
        self._counter_lock = threading.Lock()
        self.dlq_writer = _JsonlWriter("pulsar_dlq_events.jsonl")
        self.dlq_producer = None
        if self.retry_policy.enable_dlq:
            try:
                self.dlq_producer = self.client.create_producer(self.retry_policy.dlq_topic)
            except Exception as error:
                print(f"[event-consumer] dlq producer unavailable: {error}")

    def run(self, max_messages: int = 0, idle_sleep_sec: float = 0.5) -> int:
        if self.worker_count <= 1:
            return self._run_single_worker(max_messages=max_messages, idle_sleep_sec=idle_sleep_sec)
        return self._run_parallel_workers(max_messages=max_messages, idle_sleep_sec=idle_sleep_sec)

    def _run_single_worker(self, max_messages: int = 0, idle_sleep_sec: float = 0.5) -> int:
        processed = 0
        while True:
            if max_messages > 0 and processed >= max_messages:
                break
            message = None
            try:
                message = self.consumer.receive(timeout_millis=1000)
            except Exception:
                time.sleep(idle_sleep_sec)
                continue
            self.metrics.received_total += 1
            if self._process_message(message):
                processed += 1
        self.metrics.write_prometheus_file(self.metrics_path)
        return processed

    def _run_parallel_workers(self, max_messages: int = 0, idle_sleep_sec: float = 0.5) -> int:
        inbox: queue.Queue[Any] = queue.Queue(maxsize=max(8, self.queue_capacity))
        processed_ref = {"value": 0}

        def _worker() -> None:
            while True:
                item = inbox.get()
                try:
                    if item is None:
                        return
                    if self._process_message(item):
                        with self._counter_lock:
                            processed_ref["value"] += 1
                finally:
                    inbox.task_done()

        workers = [threading.Thread(target=_worker, daemon=True) for _ in range(max(1, self.worker_count))]
        for worker in workers:
            worker.start()

        while True:
            with self._counter_lock:
                done = processed_ref["value"]
            if max_messages > 0 and done >= max_messages:
                break
            message = None
            try:
                message = self.consumer.receive(timeout_millis=1000)
            except Exception:
                time.sleep(idle_sleep_sec)
                continue
            self.metrics.received_total += 1
            try:
                inbox.put(message, timeout=0.2)
            except queue.Full:
                self.metrics.queue_full_drop_total += 1
                self.consumer.negative_acknowledge(message)

        for _ in workers:
            inbox.put(None)
        inbox.join()
        for worker in workers:
            worker.join(timeout=1)

        self.metrics.write_prometheus_file(self.metrics_path)
        return processed_ref["value"]

    def _process_message(self, message: Any) -> bool:
        try:
            data = json.loads(message.data().decode("utf-8"))
            raw_payload = data.get("payload", {})
            payload = _extract_payload(raw_payload)
            evt = EventMessage(
                topic=str(data.get("topic", "")),
                payload=payload,
                ts=str(data.get("ts", datetime.now(timezone.utc).isoformat())),
            )
            self.metrics.last_lag_seconds = _compute_lag_seconds(evt.ts)
            _handle_with_retry(evt, self.handlers, self.retry_policy, self.metrics)
            self.consumer.acknowledge(message)
            self.metrics.processed_total += 1
            if self.metrics_flush_every > 0 and self.metrics.processed_total % self.metrics_flush_every == 0:
                self.metrics.write_prometheus_file(self.metrics_path)
            return True
        except Exception:
            if self.retry_policy.enable_dlq:
                self.metrics.dlq_total += 1
                self._publish_dlq(message)
                self.consumer.acknowledge(message)
            else:
                self.consumer.negative_acknowledge(message)
            return False

    def _publish_dlq(self, message: Any) -> None:
        error_info = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "raw": message.data().decode("utf-8", errors="replace"),
        }
        self.dlq_writer.write(error_info)
        if self.dlq_producer is not None:
            try:
                self.dlq_producer.send(json.dumps(error_info, ensure_ascii=False).encode("utf-8"))
            except Exception:
                pass

    def close(self) -> None:
        self.metrics.write_prometheus_file(self.metrics_path)
        if self.dlq_producer is not None:
            try:
                self.dlq_producer.close()
            except Exception:
                pass
        try:
            self.consumer.close()
        except Exception:
            pass
        try:
            self.client.close()
        except Exception:
            pass

