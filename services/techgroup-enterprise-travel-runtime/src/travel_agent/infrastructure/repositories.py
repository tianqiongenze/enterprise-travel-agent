"""Infrastructure adapters for domain ports."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import List, Optional

from ..domain.travel import TripPlan
from ..db import crud
from ..db.database import build_session_factory

logger = logging.getLogger("travel_agent.infrastructure.repositories")

_DB_TIMEOUT_S = float(os.getenv("TRAVEL_PLAN_DB_TIMEOUT_S", "30"))


class _BackgroundLoopRunner:
    """Runs persistence coroutines on a private single-threaded event loop.

    The ``TripPlanRepository`` port is synchronous (called from FastAPI
    threadpool workers and unit tests alike), while the write model
    (``db.crud`` + SQLAlchemy async engine) is coroutine based. Dispatching to
    a dedicated background loop keeps the port synchronous without re-entering
    or blocking the caller's loop, and keeps every aiosqlite/aiomysql
    connection owned by exactly one loop for its whole lifetime.
    """

    _lock = threading.Lock()
    _instance: Optional["_BackgroundLoopRunner"] = None

    @classmethod
    def instance(cls) -> "_BackgroundLoopRunner":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            name="travel-plan-db-loop",
            daemon=True,
        )
        self._thread.start()

    def run(self, coroutine):
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        return future.result(timeout=_DB_TIMEOUT_S)


class InMemoryTripPlanRepository:
    """Thread-unsafe-by-design single-process repository; dev/test and the
    degraded fallback for the async adapter."""

    def __init__(self) -> None:
        self._rows: dict[str, TripPlan] = {}

    def save(self, plan: TripPlan) -> None:
        self._rows[plan.plan_id] = plan

    def get(self, plan_id: str) -> Optional[TripPlan]:
        return self._rows.get(plan_id)

    def list_by_city(self, city: str, limit: int = 10) -> List[TripPlan]:
        rows = [plan for plan in self._rows.values() if plan.city == city]
        return sorted(rows, key=lambda plan: plan.created_at_ms, reverse=True)[:limit]


class SqlAlchemyTripPlanRepository:
    """Async adapter over the existing write model (db.crud.TripPlanRepo).

    Every port call is mirrored to the in-memory repository first so reads
    stay coherent while the row is in flight, then handed to ``db.crud`` on a
    background event loop with a real ``AsyncSession`` (insert/update via
    ``session.merge``, rehydration from ``plan_detail_json``).

    Read paths degrade to the in-memory mirror when the database is
    unavailable so a database outage never breaks the recommendation path;
    ``save`` lets the error propagate for the application service to swallow
    (a write-model outage degrades persistence, not the request).
    """

    def __init__(
        self,
        engine=None,
        session_factory=None,
        in_memory: Optional[InMemoryTripPlanRepository] = None,
    ) -> None:
        self._fallback = in_memory or InMemoryTripPlanRepository()
        if session_factory is None:
            if engine is None:
                # Share the module-level engine (built lazily from
                # TRAVEL_DB_URL) instead of opening a second pool.
                from ..db import database as db_database

                engine = db_database.engine
            session_factory = build_session_factory(engine)
        self._engine = engine
        self._session_factory = session_factory
        self._runner = _BackgroundLoopRunner.instance()

    async def _save_async(self, plan: TripPlan) -> None:
        async with self._session_factory() as session:
            await crud.TripPlanRepo.upsert_domain_plan(session, plan)

    async def _get_async(self, plan_id: str) -> Optional[TripPlan]:
        async with self._session_factory() as session:
            row = await crud.TripPlanRepo.get_domain_plan(session, plan_id)
            return None if row is None else crud.row_to_domain_plan(row)

    async def _list_async(self, city: str, limit: int) -> List[TripPlan]:
        async with self._session_factory() as session:
            rows = await crud.TripPlanRepo.list_domain_plans_by_city(session, city, limit=limit)
            plans = [crud.row_to_domain_plan(row) for row in rows]
            return [plan for plan in plans if plan is not None]

    def save(self, plan: TripPlan) -> None:
        self._fallback.save(plan)
        self._runner.run(self._save_async(plan))

    def get(self, plan_id: str) -> Optional[TripPlan]:
        try:
            plan = self._runner.run(self._get_async(plan_id))
        except Exception as error:  # noqa: BLE001 - reads degrade to the mirror
            logger.warning("trip plan read fell back to in-memory mirror: %s", error)
            return self._fallback.get(plan_id)
        if plan is not None:
            self._fallback.save(plan)
            return plan
        return self._fallback.get(plan_id)

    def list_by_city(self, city: str, limit: int = 10) -> List[TripPlan]:
        try:
            plans = self._runner.run(self._list_async(city, limit))
        except Exception as error:  # noqa: BLE001 - reads degrade to the mirror
            logger.warning("trip plan list fell back to in-memory mirror: %s", error)
            return self._fallback.list_by_city(city, limit=limit)
        if plans:
            for plan in plans:
                self._fallback.save(plan)
            return plans
        return self._fallback.list_by_city(city, limit=limit)

    def close(self) -> None:
        """Dispose the underlying engine and release its connections (e.g. the
        sqlite file lock on Windows).

        Only call when nothing else uses the engine: repositories built via
        the default path share the ``db.database`` module engine, so pair this
        with ``db.database.reset_default_engine()`` afterwards.
        """
        if self._engine is not None:
            try:
                self._runner.run(self._engine.dispose())
            except Exception as error:  # noqa: BLE001 - best-effort teardown
                logger.warning("trip plan engine dispose failed: %s", error)
