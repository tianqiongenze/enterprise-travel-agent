"""Module provides service components and helpers."""

from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Date, DECIMAL, JSON, SmallInteger
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    """
    用户核心资产表映射
    """
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="全局唯一用户ID(雪花算法)")
    phone = Column(String(20), unique=True, nullable=False, comment="手机号(加密存储)")
    nickname = Column(String(50), nullable=True, comment="昵称")
    avatar_url = Column(String(255), nullable=True, comment="头像OSS路径")
    status = Column(SmallInteger, default=1, comment="状态: 1正常 0禁用")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class TripPlan(Base):
    """
    旅游行程计划(订单)核心交易表映射
    对应 schema.sql 中的 trip_plans
    """
    __tablename__ = "trip_plans"

    plan_id = Column(BigInteger, primary_key=True, comment="行程ID(走雪花算法发号器)")
    user_id = Column(BigInteger, nullable=False, index=True, comment="用户ID(分片键 Sharding Key)")
    conversation_id = Column(String(64), nullable=True, comment="来源会话ID")
    destination = Column(String(100), nullable=False, comment="目的地")
    start_date = Column(Date, nullable=False, comment="出发日期")
    end_date = Column(Date, nullable=False, comment="结束日期")
    budget_total = Column(DECIMAL(10, 2), nullable=True, comment="总预算")
    plan_detail_json = Column(JSON, nullable=False, comment="Agent生成的结构化行程JSON(兼容MongoDB侧模式)")
    status = Column(SmallInteger, default=1, index=True, comment="状态: 1草稿 2确认出行 3已取消")
    created_at = Column(DateTime, server_default=func.now())

class AgentConversation(Base):
    """
    对话主会话记录映射
    """
    __tablename__ = "agent_conversations"

    conversation_id = Column(String(64), primary_key=True, comment="会话全局唯一ID")
    user_id = Column(BigInteger, nullable=False, index=True, comment="所属用户ID")
    title = Column(String(100), nullable=True, comment="话题摘要或生成Title")
    turn_count = Column(Integer, default=0, comment="对话轮数(用于限制超长上下文)")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

