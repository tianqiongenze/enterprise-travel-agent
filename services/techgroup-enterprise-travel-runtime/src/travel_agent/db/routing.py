"""Read/write routing for the DDD persistence path (fourth-round R2).

Follows the SQLAlchemy 2.0 official "partitioning strategies" pattern:
a custom ``AsyncSession`` subclass overrides ``get_bind`` so that writes
(flush) go to the primary engine and plain SELECTs go to the read engine.

- Primary:  ``TRAVEL_DB_URL``       (TiDB primary / local sqlite)
- Replica:  ``TRAVEL_DB_READ_URL``  (TiDB follower read; falls back to the
            primary when unset, so local dev and CI cost nothing)

TiDB side the read engine can set ``tidb_replica_read=closest-adaptive``
(via ``TRAVEL_TIDB_REPLICA_READ``) so followers serve reads without
cross-zone traffic. Stale reads for list pages go through
``stale_read_seconds`` (``tidb_read_staleness``).
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.elements import TextClause

from .database import build_engine, build_session_factory  # noqa: F401 (re-export convenience)


def read_database_url() -> str:
    """Read-replica URL; empty means "no replica configured"."""
    return os.getenv("TRAVEL_DB_READ_URL", "").strip()


def replica_read_mode() -> str:
    """TiDB ``tidb_replica_read`` mode for the read engine."""
    return os.getenv("TRAVEL_TIDB_REPLICA_READ", "closest-adaptive").strip()


def stale_read_seconds() -> int:
    """``tidb_read_staleness`` for stale-read sessions (0 = disabled)."""
    return max(0, int(os.getenv("TRAVEL_DB_STALE_READ_SECONDS", "0")))


def build_read_engine(overrides: dict[str, Any] | None = None) -> AsyncEngine | None:
    """Build the read-replica engine, or None when no replica URL is set.

    Mirrors ``database.build_engine`` but with its own pool sizing knobs and
    ``pool_pre_ping`` (replica connections can be reaped by TiDB earlier).
    """
    url = read_database_url()
    if not url:
        return None
    kwargs: dict[str, Any] = {
        "pool_size": int(os.getenv("TRAVEL_DB_READ_POOL_SIZE", "100")),
        "max_overflow": int(os.getenv("TRAVEL_DB_READ_MAX_OVERFLOW", "200")),
        "pool_recycle": int(os.getenv("TRAVEL_DB_READ_POOL_RECYCLE", "3600")),
        "pool_pre_ping": True,
    }
    # sqlite (test path) must not receive pool kwargs.
    if url.startswith("sqlite"):
        kwargs = {}
    kwargs.update(overrides or {})
    engine = create_async_engine(url, **kwargs)
    mode = replica_read_mode()
    if mode and not url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(engine.sync_engine, "connect")
        def _set_replica_read(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute(f"SET tidb_replica_read = '{mode}'")
            except Exception:
                pass  # non-TiDB backend (dev/CI): ignore
            finally:
                cursor.close()
    return engine


class _RoutingSyncSession(Session):
    """Sync session executing the actual bind routing.

    ``AsyncSession`` delegates every operation to this object, so the
    ``get_bind`` override must live here (SQLAlchemy 2.0 official
    partitioning pattern — ``session_custom_partitioning``).
    """

    def get_bind(self, mapper=None, clause=None, bind=None, **kw: Any):  # type: ignore[override]
        if bind:
            return bind
        # DML detection: writes must go to the primary. _flushing only covers
        # flush-time work, so also route text DML by inspecting the clause.
        if getattr(self, "_flushing", False):
            return self._primary_engine.sync_engine
        if self.info.get("force_primary"):
            return self._primary_engine.sync_engine
        if clause is not None:
            from sqlalchemy.sql.dml import UpdateBase

            if isinstance(clause, UpdateBase):
                return self._primary_engine.sync_engine
            if isinstance(clause, TextClause):
                # Raw SQL: sniff leading DML keywords. TextClause has no
                # structured intent, so a conservative prefix match is the
                # only signal available.
                head = (clause.text or "").lstrip().upper()
                if head.startswith(("INSERT", "UPDATE", "DELETE", "REPLACE", "MERGE", "CREATE", "DROP", "ALTER", "TRUNCATE")):
                    return self._primary_engine.sync_engine
        return self._read_engine.sync_engine


class RoutingSession(AsyncSession):
    """AsyncSession proxy produced by :class:`RoutingSessionFactory`."""

    _primary_engine: AsyncEngine
    _read_engine: AsyncEngine


class RoutingSessionFactory(sessionmaker):  # type: ignore[type-arg]
    """Session factory producing routing sessions.

    ``sync_session_class`` is the key: ``AsyncSession.execute`` delegates to
    the *sync* session object, so the ``get_bind`` override must live there
    (``class_=RoutingSession`` alone would only subclass the async proxy).
    """

    def __init__(self, primary_engine: AsyncEngine, read_engine: AsyncEngine | None) -> None:
        super().__init__(
            primary_engine,
            class_=RoutingSession,
            sync_session_class=_RoutingSyncSession,
            expire_on_commit=False,
        )
        self._primary_engine = primary_engine
        self._read_engine = read_engine or primary_engine

    def __call__(self, **kw: Any) -> RoutingSession:  # type: ignore[override]
        session: RoutingSession = super().__call__(**kw)  # type: ignore[assignment]
        sync = session.sync_session
        sync._primary_engine = self._primary_engine
        sync._read_engine = self._read_engine
        return session


def build_routing_session_factory(
    primary_engine: AsyncEngine,
    read_engine: AsyncEngine | None,
) -> sessionmaker:  # type: ignore[type-arg]
    """Compose the routing session factory (primary + optional replica)."""
    return RoutingSessionFactory(primary_engine, read_engine)  # type: ignore[return-value]


def force_primary(session: AsyncSession) -> None:
    """Mark this session to route all statements to the primary engine.

    Call before the first statement (e.g. read-modify-write flows where a
    stale replica read would race the subsequent update).
    """
    session.info["force_primary"] = True
