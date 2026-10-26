"""TDD tests for the async itinerary queue (fourth-round R5)."""

from __future__ import annotations

import asyncio

import pytest

from src.travel_agent.itinerary_queue import (
    GenerationTask,
    GenerationWorker,
    ItineraryQueue,
    reset_itinerary_queue,
)


@pytest.fixture(autouse=True)
def _clean():
    reset_itinerary_queue()
    yield
    reset_itinerary_queue()


@pytest.mark.asyncio
async def test_enqueue_dequeue_roundtrip_local():
    q = ItineraryQueue()
    assert q.mode == "local"
    task = await q.enqueue({"city": "北京", "days": 3})
    assert task.status == "queued"
    got = await asyncio.wait_for(q.dequeue(), timeout=1)
    assert got.task_id == task.task_id
    assert got.payload["city"] == "北京"


@pytest.mark.asyncio
async def test_task_status_lifecycle():
    q = ItineraryQueue()
    task = await q.enqueue({"x": 1})
    assert q.task_status(task.task_id)["status"] == "queued"
    assert q.task_status("missing") is None


@pytest.mark.asyncio
async def test_worker_drains_and_completes():
    q = ItineraryQueue()
    worker = GenerationWorker(q, generate=lambda p: {"plan": f"to-{p['city']}"}, concurrency=2)
    runner = asyncio.create_task(worker.run_forever())
    task = await q.enqueue({"city": "上海"})
    for _ in range(50):
        status = q.task_status(task.task_id)
        if status and status["status"] == "done":
            break
        await asyncio.sleep(0.02)
    worker.stop()
    runner.cancel()
    status = q.task_status(task.task_id)
    assert status["status"] == "done"


@pytest.mark.asyncio
async def test_worker_failure_marks_failed():
    q = ItineraryQueue()

    def boom(payload):
        raise ValueError("llm down")

    worker = GenerationWorker(q, generate=boom, concurrency=1)
    runner = asyncio.create_task(worker.run_forever())
    task = await q.enqueue({"city": "x"})
    for _ in range(50):
        status = q.task_status(task.task_id)
        if status and status["status"] == "failed":
            break
        await asyncio.sleep(0.02)
    worker.stop()
    runner.cancel()
    assert q.task_status(task.task_id)["status"] == "failed"
    assert "llm down" in q.task_status(task.task_id)["error"]


def test_message_serialization_roundtrip():
    task = GenerationTask(task_id="t1", payload={"a": 1})
    restored = GenerationTask.from_message(task.to_message())
    assert restored.task_id == "t1" and restored.payload == {"a": 1}


@pytest.mark.asyncio
async def test_local_queue_backpressure():
    q = ItineraryQueue()
    q._local = asyncio.Queue(maxsize=2)
    await q.enqueue({})
    await q.enqueue({})
    with pytest.raises(asyncio.QueueFull):
        q._local.put_nowait("{}")
