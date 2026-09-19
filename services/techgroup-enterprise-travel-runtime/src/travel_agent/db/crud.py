"""Module provides service components and helpers."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .models import TripPlan, User
from typing import Optional, List

class TripPlanRepo:
    """
    持久化仓储层 (Data Access Object)
    专门处理复杂旅游数据的入库与检索落地。
    通过异步处理最大化释放 Python 层的 I/O 夯力。
    """
    
    @staticmethod
    async def create_plan(session: AsyncSession, user_id: int, destination: str, start_date, end_date, budget: float, detail_dict: dict) -> TripPlan:
        """
        Agent 完成推理后，通过该方法写入最终结果 (Write Model)
        """
        import time
        # TODO: 现实中此处替换为分布式雪花算法发号器服务获取ID
        mock_snowflake_id = int(time.time() * 1000)
        
        new_plan = TripPlan(
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
    async def get_plans_by_user(session: AsyncSession, user_id: int, limit: int = 10) -> List[TripPlan]:
        """
        根据用户查询历史生成订单 (Query Model, 配合 Redis Cache)
        这部分一般需要增加读库(从库)的路由策略或缓存直接命中间件。
        """
        stmt = select(TripPlan).where(TripPlan.user_id == user_id).order_by(TripPlan.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

class UserRepo:
    """
    用户领域操作模型
    """
    @staticmethod
    async def get_user_by_phone(session: AsyncSession, phone: str) -> Optional[User]:
        stmt = select(User).where(User.phone == phone)
        result = await session.execute(stmt)
        return result.scalars().first()

