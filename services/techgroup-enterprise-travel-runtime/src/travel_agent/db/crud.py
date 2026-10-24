"""Module provides service components and helpers."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ..domain.travel import (
    Budget,
    HotelOption,
    Preference,
    TransportOption,
    TripPlan,
)
from .models import TripPlan as TripPlanORM
from .models import User

# 领域状态 -> trip_plans.status (1草稿 2确认出行 3已取消)
_DOMAIN_STATUS_TO_ORM = {"draft": 1, "confirmed": 2, "cancelled": 3}
_ORM_STATUS_TO_DOMAIN = {code: name for name, code in _DOMAIN_STATUS_TO_ORM.items()}


def _plan_id_to_numeric_pk(plan_id: str) -> int:
    """Deterministically map the 16-hex domain plan_id into a signed BIGINT PK.

    Domain plan ids (``uuid4().hex[:16]``) are 64-bit hex strings; the ORM
    primary key is a signed BigInteger, so shift right by one bit (63 usable
    bits). Non-hex ids (legacy/aggregated callers) fall back to a stable hash.
    The original hex id is always preserved in ``plan_detail_json`` and
    verified again on load, so a (2^-63) hash collision can never silently
    return the wrong aggregate.
    """
    try:
        return int(plan_id, 16) >> 1
    except ValueError:
        import hashlib

        return int(hashlib.sha256(plan_id.encode("utf-8")).hexdigest()[:15], 16)


def domain_plan_to_row(plan: TripPlan, user_id: int = 0) -> TripPlanORM:
    """Map a domain TripPlan aggregate onto the trip_plans ORM row.

    The ORM row is a queryable projection (destination/status/dates for SQL
    filters); the full aggregate - value objects, options, itinerary and the
    recorded domain events - lives in ``plan_detail_json`` so a reload is
    byte-faithful.
    """
    start = datetime.fromtimestamp(plan.created_at_ms / 1000.0, tz=timezone.utc).date()
    detail: Dict[str, Any] = {
        "plan_id": plan.plan_id,
        "city": plan.city,
        "days": plan.days,
        "travelers": plan.travelers,
        "budget": plan.budget.amount,
        "preferences": [str(p) for p in plan.preferences],
        "membership_tier": plan.membership_tier,
        "status": plan.status,
        "created_at_ms": plan.created_at_ms,
        "hotel_options": [
            {"name": h.name, "score": h.score, "price": h.price, "reason": h.reason}
            for h in plan.hotel_options
        ],
        "transport_options": [
            {"name": t.name, "score": t.score, "price": t.price, "reason": t.reason}
            for t in plan.transport_options
        ],
        "itinerary": list(plan.itinerary),
        "events": list(plan.events),
    }
    return TripPlanORM(
        plan_id=_plan_id_to_numeric_pk(plan.plan_id),
        user_id=user_id,
        destination=plan.city[:100],
        start_date=start,
        end_date=start + timedelta(days=max(0, plan.days - 1)),
        budget_total=Decimal(str(round(float(plan.budget.amount), 2))),
        plan_detail_json=detail,
        status=_DOMAIN_STATUS_TO_ORM.get(plan.status, 1),
    )


def row_to_domain_plan(row: TripPlanORM) -> Optional[TripPlan]:
    """Rehydrate the domain aggregate from ``plan_detail_json``.

    Returns ``None`` for rows written outside the domain write model (e.g.
    ``db.crud.TripPlanRepo.create_plan`` mock-snowflake rows) - those carry no
    domain plan_id in their detail JSON.
    """
    detail = dict(row.plan_detail_json or {})
    plan_id = str(detail.get("plan_id", ""))
    if not plan_id:
        return None
    return TripPlan(
        city=str(detail.get("city", row.destination)),
        days=int(detail.get("days", 1)),
        budget=Budget(float(detail.get("budget", 0) or 0) or 1.0),
        travelers=int(detail.get("travelers", 1)),
        preferences=[Preference(str(name)) for name in detail.get("preferences", [])],
        membership_tier=str(detail.get("membership_tier", "basic")),
        plan_id=plan_id,
        created_at_ms=int(detail.get("created_at_ms", 0)),
        status=str(_ORM_STATUS_TO_DOMAIN.get(row.status, detail.get("status", "draft"))),
        hotel_options=[
            HotelOption(
                name=str(item.get("name", "")),
                score=float(item.get("score", 0.0) or 0.0),
                price=float(item.get("price", 0.0) or 0.0),
                reason=str(item.get("reason", "")),
            )
            for item in detail.get("hotel_options", [])
        ],
        transport_options=[
            TransportOption(
                name=str(item.get("name", "")),
                score=float(item.get("score", 0.0) or 0.0),
                price=float(item.get("price", 0.0) or 0.0),
                reason=str(item.get("reason", "")),
            )
            for item in detail.get("transport_options", [])
        ],
        itinerary=list(detail.get("itinerary", [])),
        events=list(detail.get("events", [])),
    )


class TripPlanRepo:
    """
    持久化仓储层 (Data Access Object)
    专门处理复杂旅游数据的入库与检索落地。
    通过异步处理最大化释放 Python 层的 I/O 夯力。
    """

    @staticmethod
    async def create_plan(session: AsyncSession, user_id: int, destination: str, start_date, end_date, budget: float, detail_dict: dict) -> TripPlanORM:
        """
        Agent 完成推理后，通过该方法写入最终结果 (Write Model)
        """
        import time
        # TODO: 现实中此处替换为分布式雪花算法发号器服务获取ID
        mock_snowflake_id = int(time.time() * 1000)

        new_plan = TripPlanORM(
            plan_id=mock_snowflake_id,
            user_id=user_id,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            budget_total=budget,
            plan_detail_json=detail_dict, # 自动转JSON入库
            status=1
        )
        session.add(new_plan)
        await session.commit()
        await session.refresh(new_plan)
        return new_plan

    @staticmethod
    async def get_plans_by_user(session: AsyncSession, user_id: int, limit: int = 10) -> List[TripPlanORM]:
        """
        根据用户查询历史生成订单 (Query Model, 配合 Redis Cache)
        这部分一般需要增加读库(从库)的路由策略或缓存直接命中间件。
        """
        stmt = select(TripPlanORM).where(TripPlanORM.user_id == user_id).order_by(TripPlanORM.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # DDD domain-aggregate write model (used by
    # infrastructure.repositories.SqlAlchemyTripPlanRepository).
    # ------------------------------------------------------------------

    @staticmethod
    async def upsert_domain_plan(session: AsyncSession, plan: TripPlan, user_id: int = 0) -> TripPlanORM:
        """Insert or update the projection row for a domain TripPlan aggregate.

        Uses ``session.merge`` keyed on the deterministic numeric PK derived
        from the domain plan_id, so re-saving a progressed aggregate (e.g.
        after ``confirm()``) updates status and detail JSON in place.
        """
        row = domain_plan_to_row(plan, user_id=user_id)
        merged = await session.merge(row)
        await session.commit()
        return merged

    @staticmethod
    async def get_domain_plan(session: AsyncSession, plan_id: str) -> Optional[TripPlanORM]:
        stmt = select(TripPlanORM).where(TripPlanORM.plan_id == _plan_id_to_numeric_pk(plan_id))
        result = await session.execute(stmt)
        for row in result.scalars().all():
            detail = dict(row.plan_detail_json or {})
            if str(detail.get("plan_id", "")) == plan_id:
                return row
        return None

    @staticmethod
    async def list_domain_plans_by_city(session: AsyncSession, city: str, limit: int = 10) -> List[TripPlanORM]:
        # Recent-first like the in-memory repository (created_at desc), with
        # the derived PK as a stable tiebreaker within the same second.
        stmt = (
            select(TripPlanORM)
            .where(TripPlanORM.destination == city)
            .order_by(TripPlanORM.created_at.desc(), TripPlanORM.plan_id.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = []
        for row in result.scalars().all():
            detail = dict(row.plan_detail_json or {})
            if detail.get("city") == city:
                rows.append(row)
        return rows

class UserRepo:
    """
    用户领域操作模型
    """
    @staticmethod
    async def get_user_by_phone(session: AsyncSession, phone: str) -> Optional[User]:
        stmt = select(User).where(User.phone == phone)
        result = await session.execute(stmt)
        return result.scalars().first()
