"""Module provides service components and helpers.

Async engine layer for the DDD persistence path:

- ``build_engine`` / ``build_session_factory`` are scheme-aware factories used
  by ``infrastructure.repositories.SqlAlchemyTripPlanRepository`` and by the
  persistence integration test (``TRAVEL_DB_URL=sqlite+aiosqlite:///...``).
- The module-level ``engine`` / ``async_session`` pair (used by
  ``get_db_session``) is built lazily from ``TRAVEL_DB_URL`` so importing this
  module never requires the MySQL driver to be installed (relevant for the
  sqlite-only test path).
"""

import os
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 获取数据库连接URL，支持向MySQL 8.0/TiDB连接 (高并发场景推荐TiDB并走HAProxy)
# 使用aiomysql作为异步驱动，适配FastAPI/Uvicorn协程体系
DEFAULT_DATABASE_URL = (
    "mysql+aiomysql://root:password@127.0.0.1:3306/travel_agent_db?charset=utf8mb4"
)

# 创建异步SQLAlchemy引擎的公共参数：
# pool_size和max_overflow是应对高并发的重要参数 (配置连接池)
_MYSQL_POOL_KWARGS: Dict[str, Any] = {
    "pool_size": 100,    # 基础连接池大小，适应10万级QPS网关层分流后的核心压力
    "max_overflow": 200,  # 流量洪峰时的最大溢出连接数
    "pool_recycle": 3600,  # 防止数据库自动断开，定期回收
}


def current_database_url() -> str:
    return os.getenv("TRAVEL_DB_URL", DEFAULT_DATABASE_URL)


def _engine_kwargs(url: str) -> Dict[str, Any]:
    """Engine kwargs must be dialect-specific.

    The MySQL/TiDB pool sizing must never leak into the sqlite path: sqlite
    (``sqlite+aiosqlite://``) keeps its own per-connection threads and pool
    semantics, so it is created with no pool arguments at all.
    """
    scheme = url.split("://", 1)[0].lower()
    if scheme.startswith("sqlite"):
        return {}
    return dict(_MYSQL_POOL_KWARGS)


def build_engine(url: Optional[str] = None, **overrides: Any) -> AsyncEngine:
    """Scheme-aware async engine factory (mysql+aiomysql / sqlite+aiosqlite)."""
    url = url or current_database_url()
    kwargs: Dict[str, Any] = {"echo": False}
    kwargs.update(_engine_kwargs(url))
    kwargs.update(overrides)
    return create_async_engine(url, **kwargs)


def build_session_factory(engine: AsyncEngine) -> sessionmaker:  # type: ignore[type-arg]
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# 异步Session工厂与engine默认实例按需构建（PEP 562 module __getattr__），
# 避免在仅安装 sqlite 驱动的环境导入本模块时因缺少 aiomysql 而失败。
_default_engine: Optional[AsyncEngine] = None
_default_session_factory: Optional[sessionmaker] = None  # type: ignore[type-arg]


def reset_default_engine() -> None:
    """Drop the lazily built default engine/session factory.

    Used by tests (and hot reconfiguration) so the next access to
    ``engine`` / ``async_session`` re-reads ``TRAVEL_DB_URL``. Callers are
    responsible for disposing any engine they received earlier.
    """
    global _default_engine, _default_session_factory
    _default_engine = None
    _default_session_factory = None


def _build_default_pair() -> AsyncEngine:
    global _default_engine, _default_session_factory
    if _default_engine is None:
        _default_engine = build_engine()
        _default_session_factory = build_session_factory(_default_engine)
    return _default_engine


def __getattr__(name: str) -> Any:
    if name == "engine":
        return _build_default_pair()
    if name == "async_session":
        _build_default_pair()
        assert _default_session_factory is not None
        return _default_session_factory
    if name == "DATABASE_URL":
        return current_database_url()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# 基础模型类
Base = declarative_base()


# 依赖注入快捷函数
async def get_db_session() -> AsyncSession: # type: ignore
    """
    提供给各种Agent或者FastAPI路由使用的数据库依赖
    """
    async with async_session() as session:
        yield session
