"""Module provides service components and helpers."""

import importlib
import sys
import unittest
from dataclasses import dataclass
from unittest.mock import patch


class _FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalarResult(self._rows)


class _FakeAsyncSession:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.added = []
        self.execute_calls = 0
        self.committed = False
        self.refreshed = False

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.committed = True

    async def refresh(self, _value):
        self.refreshed = True

    async def execute(self, _stmt):
        self.execute_calls += 1
        return _FakeExecuteResult(self.rows)


@dataclass
class _PlanRow:
    plan_id: int
    user_id: int
    destination: str


class DbCrudTestCase(unittest.IsolatedAsyncioTestCase):
    def _load_crud_module(self):
        for name in [
            "src.travel_agent.db.crud",
            "src.travel_agent.db.models",
            "src.travel_agent.db.database",
        ]:
            sys.modules.pop(name, None)

        with patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=object()):
            return importlib.import_module("src.travel_agent.db.crud")

    async def test_create_plan_persists_and_refreshes(self) -> None:
        crud = self._load_crud_module()
        session = _FakeAsyncSession()

        with patch("time.time", return_value=1700000000.0):
            plan = await crud.TripPlanRepo.create_plan(
                session=session,
                user_id=7,
                destination="Shanghai",
                start_date="2026-05-01",
                end_date="2026-05-03",
                budget=1999.0,
                detail_dict={"days": 3},
            )

        self.assertEqual(len(session.added), 1)
        self.assertTrue(session.committed)
        self.assertTrue(session.refreshed)
        self.assertEqual(plan.user_id, 7)
        self.assertEqual(plan.destination, "Shanghai")
        self.assertEqual(plan.plan_id, 1700000000000)

    async def test_get_plans_by_user_returns_scalars(self) -> None:
        crud = self._load_crud_module()
        rows = [
            _PlanRow(plan_id=1, user_id=9, destination="Beijing"),
            _PlanRow(plan_id=2, user_id=9, destination="Chengdu"),
        ]
        session = _FakeAsyncSession(rows=rows)

        plans = await crud.TripPlanRepo.get_plans_by_user(session=session, user_id=9, limit=5)

        self.assertEqual(session.execute_calls, 1)
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].destination, "Beijing")


if __name__ == "__main__":
    unittest.main()

