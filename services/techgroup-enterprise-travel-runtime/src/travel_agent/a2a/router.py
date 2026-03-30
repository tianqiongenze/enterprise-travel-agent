"""Module provides service components and helpers."""

import importlib
import json
import os
import time
from typing import Dict, List, Optional, Protocol

from .protocol import A2AMessage, new_message


class A2ARouter:
    def __init__(self, transport: Optional["A2ATransport"] = None) -> None:
        self.transport = transport or _build_transport_from_env()

    def send(
        self,
        sender: str,
        receiver: str,
        topic: str,
        payload: Dict[str, object],
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> A2AMessage:
        message = new_message(
            sender,
            receiver,
            topic,
            payload,
            correlation_id=correlation_id,
            metadata=metadata,
        )
        self.transport.publish(message)
        return message

    def inbox(self, receiver: str) -> List[Dict[str, object]]:
        return self.transport.consume(receiver)


class A2ATransport(Protocol):
    def publish(self, message: A2AMessage) -> None:
        ...

    def consume(self, receiver: str, limit: int = 100) -> List[Dict[str, object]]:
        ...


class RedisA2ATransport:
    def __init__(self) -> None:
        redis_module = importlib.import_module("redis")
        redis_url = os.getenv("TRAVEL_A2A_REDIS_URL", os.getenv("TRAVEL_REDIS_URL", "redis://127.0.0.1:7000"))
        self.key_prefix = os.getenv("TRAVEL_A2A_KEY_PREFIX", "a2a:stream")
        self.max_len = int(os.getenv("TRAVEL_A2A_MAX_LEN", "10000"))
        self.group = os.getenv("TRAVEL_A2A_STREAM_GROUP", "a2a-consumers")
        self.pending_retry_idle_ms = int(os.getenv("TRAVEL_A2A_PENDING_RETRY_IDLE_MS", "10000"))
        self.pending_retry_batch = int(os.getenv("TRAVEL_A2A_PENDING_RETRY_BATCH", "50"))
        self.read_batch = int(os.getenv("TRAVEL_A2A_READ_BATCH", "100"))
        self.read_block_ms = int(os.getenv("TRAVEL_A2A_READ_BLOCK_MS", "100"))
        self.client = redis_module.Redis.from_url(redis_url, decode_responses=True)
        self.consumer_prefix = os.getenv("TRAVEL_A2A_CONSUMER_PREFIX", "a2a")
        self.audit_mirror = PulsarA2AAuditMirror()

    def publish(self, message: A2AMessage) -> None:
        key = self._receiver_key(message.receiver)
        body = json.dumps(message.__dict__, ensure_ascii=False)
        self._ensure_group(key)
        self.client.xadd(key, {"body": body}, maxlen=self.max_len, approximate=True)
        self.audit_mirror.publish(message)

    def consume(self, receiver: str, limit: int = 100) -> List[Dict[str, object]]:
        key = self._receiver_key(receiver)
        self._ensure_group(key)
        consumer = f"{self.consumer_prefix}:{receiver}"
        retried = self._retry_stuck_pending(key, consumer)
        batch = max(1, min(limit, self.read_batch))
        rows = self.client.xreadgroup(
            groupname=self.group,
            consumername=consumer,
            streams={key: ">"},
            count=batch,
            block=max(1, self.read_block_ms),
        )
        messages: List[Dict[str, object]] = []
        ack_ids: List[str] = []
        for entry_id, fields in retried:
            row = str(fields.get("body", ""))
            try:
                payload = json.loads(row)
            except Exception:
                ack_ids.append(entry_id)
                continue
            if isinstance(payload, dict):
                messages.append(payload)
            ack_ids.append(entry_id)
        for _, entries in rows:
            for entry_id, fields in entries:
                row = str(fields.get("body", ""))
                try:
                    payload = json.loads(row)
                except Exception:
                    ack_ids.append(entry_id)
                    continue
                if isinstance(payload, dict):
                    messages.append(payload)
                ack_ids.append(entry_id)
        if ack_ids:
            pipe = self.client.pipeline(transaction=False)
            for entry_id in ack_ids:
                pipe.xack(key, self.group, entry_id)
            pipe.execute()
        return messages

    def _retry_stuck_pending(self, key: str, consumer: str) -> List[tuple[str, Dict[str, object]]]:
        try:
            rows = self.client.xautoclaim(
                key,
                self.group,
                consumer,
                min_idle_time=max(1000, self.pending_retry_idle_ms),
                start_id="0-0",
                count=max(1, self.pending_retry_batch),
            )
        except Exception:
            return []
        if not rows or len(rows) < 2:
            return []
        claimed = rows[1]
        return claimed

    def _ensure_group(self, key: str) -> None:
        try:
            self.client.xgroup_create(key, self.group, id="0", mkstream=True)
        except Exception:
            return

    def _receiver_key(self, receiver: str) -> str:
        day_slot = time.strftime("%Y%m%d")
        return f"{self.key_prefix}:{receiver}:{day_slot}"


class MockDistributedA2ATransport:
    """Test-only transport that mimics remote queue semantics in-memory."""

    def __init__(self) -> None:
        self._rows: Dict[str, List[Dict[str, object]]] = {}

    def publish(self, message: A2AMessage) -> None:
        key = message.receiver
        self._rows.setdefault(key, []).insert(0, dict(message.__dict__))

    def consume(self, receiver: str, limit: int = 100) -> List[Dict[str, object]]:
        return self._rows.get(receiver, [])[:limit]


def _build_transport_from_env() -> A2ATransport:
    mode = os.getenv("TRAVEL_A2A_TRANSPORT", "redis").strip().lower()
    if mode in {"mock", "mock-distributed", "test"}:
        return MockDistributedA2ATransport()
    return RedisA2ATransport()


class PulsarA2AAuditMirror:
    def __init__(self) -> None:
        self.enabled = os.getenv("TRAVEL_A2A_AUDIT_MIRROR_PULSAR", "false").strip().lower() == "true"
        self.producer = None
        self.client = None
        if not self.enabled:
            return
        try:
            pulsar = importlib.import_module("pulsar")
            service_url = os.getenv("PULSAR_SERVICE_URL", "pulsar://127.0.0.1:6650")
            topic = os.getenv("TRAVEL_A2A_AUDIT_TOPIC", "persistent://public/default/travel-agent.a2a.audit")
            self.client = pulsar.Client(service_url)
            self.producer = self.client.create_producer(topic)
        except Exception as error:
            self.enabled = False
            print(f"[a2a] pulsar mirror disabled: {error}")

    def publish(self, message: A2AMessage) -> None:
        if not self.enabled or self.producer is None:
            return
        try:
            payload = json.dumps({"topic": "a2a." + message.topic, "payload": message.__dict__}, ensure_ascii=False).encode("utf-8")
            self.producer.send(payload)
        except Exception:
            return


