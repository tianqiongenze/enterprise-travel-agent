"""Module handles event bus interactions."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict


class EventBus:
    def publish(self, topic: str, payload: Dict[str, object]) -> None:
        raise NotImplementedError

    def close(self) -> None:
        return None


class LocalEventBus(EventBus):
    def __init__(self) -> None:
        self.events = []

    def publish(self, topic: str, payload: Dict[str, object]) -> None:
        self.events.append({"topic": topic, "payload": payload})


class PulsarEventBus(EventBus):
    def __init__(self) -> None:
        import pulsar  # type: ignore

        service_url = os.getenv("PULSAR_SERVICE_URL", "pulsar://127.0.0.1:6650")
        self.namespace = os.getenv("PULSAR_NAMESPACE", "public/default")
        self.prefix = os.getenv("TRAVEL_PULSAR_TOPIC_PREFIX", "travel-agent")
        self._pulsar = pulsar
        self.client = pulsar.Client(service_url)
        self.producers: Dict[str, Any] = {}

    def _topic_name(self, topic: str) -> str:
        if topic.startswith("persistent://"):
            return topic
        return f"persistent://{self.namespace}/{self.prefix}.{topic}"

    def _get_producer(self, topic: str):
        full_name = self._topic_name(topic)
        producer = self.producers.get(full_name)
        if producer is not None:
            return producer
        producer = self.client.create_producer(full_name)
        self.producers[full_name] = producer
        return producer

    def publish(self, topic: str, payload: Dict[str, object]) -> None:
        message = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "payload": payload,
        }
        producer = self._get_producer(topic)
        producer.send(json.dumps(message, ensure_ascii=False).encode("utf-8"))

    def close(self) -> None:
        for producer in self.producers.values():
            try:
                closer = getattr(producer, "close", None)
                if callable(closer):
                    closer()
            except Exception:
                pass
        try:
            self.client.close()
        except Exception:
            pass


def build_event_bus_from_env() -> EventBus:
    backend = os.getenv("TRAVEL_EVENT_BUS", "pulsar").strip().lower()
    strict = os.getenv("TRAVEL_EVENT_BUS_STRICT", "false").strip().lower() == "true"
    if backend in {"", "none", "local"}:
        return LocalEventBus()
    if backend == "pulsar":
        try:
            return PulsarEventBus()
        except Exception as error:
            if strict:
                raise RuntimeError(f"TRAVEL_EVENT_BUS=pulsar init failed: {error}") from error
            print(f"[event-bus] pulsar unavailable, fallback to local: {error}")
            return LocalEventBus()
    raise RuntimeError(f"Unsupported TRAVEL_EVENT_BUS: {backend}")

