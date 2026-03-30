"""Module provides service components and helpers."""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# 获取数据库连接URL，支持向MySQL 8.0/TiDB连接 (高并发场景推荐TiDB并走HAProxy)
# 使用aiomysql作为异步驱动，适配FastAPI/Uvicorn协程体系
DATABASE_URL = os.getenv(
    "TRAVEL_DB_URL", 
    "mysql+aiomysql://root:password@127.0.0.1:3306/travel_agent_db?charset=utf8mb4"
)

# 创建异步SQLAlchemy引擎
# pool_size和max_overflow是应对高并发的重要参数 (配置连接池)
engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # 生产环境关闭echo，防止SQL刷屏日志影响性能
    pool_size=100,       # 基础连接池大小，适应10万级QPS网关层分流后的核心压力
    max_overflow=200,    # 流量洪峰时的最大溢出连接数
    pool_recycle=3600,   # 防止数据库自动断开，定期回收
)

# 异步Session工厂
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 基础模型类
Base = declarative_base()

# 依赖注入快捷函数
async def get_db_session() -> AsyncSession: # type: ignore
    """
    提供给各种Agent或者FastAPI路由使用的数据库依赖
    """
    async with async_session() as session:
        yield session

