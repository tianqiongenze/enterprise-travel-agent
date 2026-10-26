"""TDD tests for read/write routing (fourth-round R2, plan §四.R2).

Strategy: two sqlite engines (primary + read replica). Writes must hit the
primary; plain SELECTs must hit the read engine. When TRAVEL_DB_READ_URL is
unset everything falls back to the primary (zero-cost local/CI default).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.travel_agent.db.routing import (
    RoutingSessionFactory,
    build_read_engine,
    build_routing_session_factory,
    read_database_url,
)


@pytest.fixture()
def two_engines(tmp_path):
    import asyncio

    async def _make():
        primary = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/primary.db")
        read = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/replica.db")
        from sqlalchemy import text as _t
        for engine, name in ((primary, "primary"), (read, "replica")):
            async with engine.begin() as conn:
                await conn.execute(_t("CREATE TABLE IF NOT EXISTS marker (src TEXT)"))
                await conn.execute(_t("DELETE FROM marker"))
                await conn.execute(_t("INSERT INTO marker (src) VALUES (:v)"), {"v": name})
        return primary, read

    primary, read = asyncio.run(_make())
    yield primary, read

    async def _dispose():
        await primary.dispose()
        await read.dispose()

    asyncio.run(_dispose())


@pytest.mark.asyncio
async def test_no_replica_url_falls_back_to_primary(monkeypatch):
    monkeypatch.delenv("TRAVEL_DB_READ_URL", raising=False)
    assert read_database_url() == ""
    assert build_read_engine() is None


@pytest.mark.asyncio
async def test_reads_hit_replica_and_writes_hit_primary(two_engines):
    primary, read = two_engines
    factory = build_routing_session_factory(primary, read)

    async with factory() as session:
        # Plain SELECT → replica marker
        row = (await session.execute(text("SELECT src FROM marker"))).scalar_one()
        assert row == "replica"

    async with factory() as session:
        # Write path: the INSERT is a DML statement — SQLAlchemy marks the
        # session flushing during execute, so get_bind resolves the primary.
        await session.execute(text("INSERT INTO marker (src) VALUES ('written')"))
        await session.commit()

    # Verify the write landed on the primary engine (replica marker unchanged).
    async with RoutingSessionFactory(primary, None)() as s:
        rows = (await s.execute(text("SELECT src FROM marker"))).scalars().all()
        assert "written" in rows, "write must land on primary engine"
    async with RoutingSessionFactory(read, None)() as s:
        rows = (await s.execute(text("SELECT src FROM marker"))).scalars().all()
        assert rows == ["replica"], "replica must not see the write"


@pytest.mark.asyncio
async def test_routing_factory_is_sessionmaker_compatible(two_engines):
    primary, read = two_engines
    factory = RoutingSessionFactory(primary, read)
    assert factory._read_engine is read.sync_engine or factory._read_engine is read
    assert factory._primary_engine is primary or factory._primary_engine is primary.sync_engine
