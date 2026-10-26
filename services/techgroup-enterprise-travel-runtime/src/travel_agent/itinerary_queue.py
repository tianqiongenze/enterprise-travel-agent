"""Async itinerary generation queue (fourth-round R5, plan §四.R5).

Peak-shaving: at 1M concurrent users the AI generation path cannot run
synchronously (80k concurrent LLM calls). The sync face returns the
itinerary skeleton (or cached result) immediately and enqueues the full
generation as a task; a worker pool drains the queue.

Carrier selection mirrors the event-bus convention:
- TRAVEL_ITINERARY_QUEUE=local  → in-process asyncio.Queue (dev/CI/tests)
- pulsar (default)              → Pulsar topic via existing event bus client
Redis Streams is deliberately not used here (A2A already owns that lane).

KEDA scales the worker deployment on the Pulsar subscription backlog;
the worker entrypoint is ``python -m travel_agent.itinerary_worker``.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class GenerationTask:
    task_id: str
    payload: Dict[str, Any]
    enqueued_at: float = field(default_factory=time.time)
    status: str = "queued"  # queued|running|done|failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_message(self) -> str:
        return json.dumps(
            {"task_id": self.task_id, "payload": self.payload, "enqueued_at": self.enqueued_at},
            ensure_ascii=False,
        )

    @staticmethod
    def from_message(raw: str) -> "GenerationTask":
        row = json.loads(raw)
        return GenerationTask(task_id=row["task_id"], payload=row["payload"], enqueued_at=row["enqueued_at"])


class ItineraryQueue:
    """Queue facade: local asyncio queue or Pulsar producer."""

    TOPIC = "persistent://public/default/travel-agent.itinerary.tasks"

    def __init__(self) -> None:
        self.backend = os.getenv("TRAVEL_ITINERARY_QUEUE", "local").strip().lower()
        self._local: asyncio.Queue[str] = asyncio.Queue(maxsize=self._max_queue())
        self._producer = None
        self._tasks: Dict[str, GenerationTask] = {}
        if self.backend in {"pulsar", ""}:
            self._producer = self._build_pulsar_producer()

    @staticmethod
    def _max_queue() -> int:
        return int(os.getenv("TRAVEL_ITINERARY_QUEUE_MAX", "20000"))

    def _build_pulsar_producer(self):
        try:
            import pulsar  # type: ignore

            client = pulsar.Client(os.getenv("TRAVEL_PULSAR_URL", "pulsar://127.0.0.1:6650"))
            return client.create_producer(self.TOPIC)
        except Exception as error:
            print(f"[itinerary-queue] pulsar unavailable, fallback local: {error}")
            return None

    @property
    def mode(self) -> str:
        return "pulsar" if self._producer is not None else "local"

    async def enqueue(self, payload: Dict[str, Any]) -> GenerationTask:
        task = GenerationTask(task_id=uuid.uuid4().hex, payload=payload)
        self._tasks[task.task_id] = task
        if self._producer is not None:
            try:
                await asyncio.to_thread(self._producer.send, task.to_message().encode())
                return task
            except Exception:
                pass  # degrade to local queue
        await self._local.put(task.to_message())
        return task

    async def dequeue(self) -> GenerationTask:
        raw = await self._local.get()
        task = GenerationTask.from_message(raw)
        # Re-use the registered instance so status transitions are visible to
        # task_status() (from_message would create a detached copy).
        registered = self._tasks.get(task.task_id)
        return registered if registered is not None else task

    def task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return {"task_id": task.task_id, "status": task.status, "error": task.error}


class GenerationWorker:
    """Drains the local queue (Pulsar path uses the go-fanout consumer)."""

    def __init__(
        self,
        queue: ItineraryQueue,
        generate: Callable[[Dict[str, Any]], Dict[str, Any]],
        concurrency: int = 4,
    ) -> None:
        self.queue = queue
        self.generate = generate
        self.concurrency = concurrency
        self._running = False

    async def run_forever(self) -> None:
        self._running = True
        workers = [asyncio.create_task(self._one()) for _ in range(self.concurrency)]
        await asyncio.gather(*workers)

    def stop(self) -> None:
        self._running = False

    async def _one(self) -> None:
        while self._running:
            try:
                task = await asyncio.wait_for(self.queue.dequeue(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            task.status = "running"
            try:
                task.result = await asyncio.to_thread(self.generate, task.payload)
                task.status = "done"
            except Exception as error:  # noqa: BLE001
                task.status = "failed"
                task.error = str(error)


_queue: Optional[ItineraryQueue] = None


def get_itinerary_queue() -> ItineraryQueue:
    global _queue
    if _queue is None:
        _queue = ItineraryQueue()
    return _queue


def reset_itinerary_queue() -> None:
    global _queue
    _queue = None
