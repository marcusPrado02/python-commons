"""SQLAlchemy adapter – SQLAlchemyEventStore (§27.10)."""
from __future__ import annotations

import json
from typing import Any

from mp_commons.application.event_sourcing.store import EventStore, OptimisticConcurrencyError
from mp_commons.application.event_sourcing.stored_event import StoredEvent


class SQLAlchemyEventStore(EventStore):
    """Append-only SQLAlchemy event store with optimistic concurrency.

    All events are persisted in a single ``domain_events`` table.  The
    ``(stream_id, version)`` pair is declared ``UNIQUE`` — the database
    itself enforces that no two events share the same version within a
    stream, providing a second line of defence against concurrent writes.

    The store **does not** define or migrate the table automatically.  Call
    :meth:`create_table` once (e.g. in your app startup or Alembic migration)
    before using the store.

    Parameters
    ----------
    session:
        An :class:`~sqlalchemy.ext.asyncio.AsyncSession` (or any async
        session-like object that supports ``execute``, ``add``, etc.).
    """

    TABLE_NAME = "domain_events"

    def __init__(self, session: Any) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    @classmethod
    async def create_table(cls, bind: Any) -> None:
        """Create the ``domain_events`` table if it does not exist.

        Parameters
        ----------
        bind:
            An :class:`~sqlalchemy.ext.asyncio.AsyncEngine` or synchronous
            :class:`~sqlalchemy.engine.Engine`.
        """
        from sqlalchemy import (  # type: ignore[import-untyped]
            Column,
            DateTime,
            Integer,
            LargeBinary,
            MetaData,
            String,
            Table,
            Text,
            UniqueConstraint,
        )

        meta = MetaData()
        Table(
            cls.TABLE_NAME,
            meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("stream_id", String(256), nullable=False, index=True),
            Column("version", Integer, nullable=False),
            Column("event_type", String(256), nullable=False),
            Column("payload", LargeBinary, nullable=False),
            Column("metadata_json", Text, nullable=False, default="{}"),
            Column("occurred_at", DateTime(timezone=True), nullable=False),
            UniqueConstraint("stream_id", "version", name="uq_domain_events_stream_version"),
        )
        try:
            async with bind.begin() as conn:
                await conn.run_sync(meta.create_all)
        except AttributeError:
            meta.create_all(bind)

    # ------------------------------------------------------------------
    # EventStore interface
    # ------------------------------------------------------------------

    async def append(
        self,
        stream_id: str,
        events: list[StoredEvent],
        expected_version: int,
    ) -> None:
        """Append *events* to *stream_id*, enforcing optimistic locking."""
        from sqlalchemy import column, func, insert, select, table  # type: ignore[import-untyped]

        t = table(
            self.TABLE_NAME,
            column("id"),
            column("stream_id"),
            column("version"),
            column("event_type"),
            column("payload"),
            column("metadata_json"),
            column("occurred_at"),
        )
        count_stmt = (
            select(func.count())
            .select_from(t)
            .where(column("stream_id") == stream_id)
        )
        actual_version: int = (await self._session.execute(count_stmt)).scalar() or 0

        if actual_version != expected_version:
            raise OptimisticConcurrencyError(stream_id, expected_version, actual_version)

        for ev in events:
            stmt = insert(t).values(
                stream_id=ev.stream_id,
                version=ev.version,
                event_type=ev.event_type,
                payload=ev.payload,
                metadata_json=json.dumps(ev.metadata),
                occurred_at=ev.occurred_at,
            )
            await self._session.execute(stmt)

    async def load(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> list[StoredEvent]:
        """Return all events for *stream_id* with ``version > from_version``."""
        from sqlalchemy import column, select, table  # type: ignore[import-untyped]

        t = table(
            self.TABLE_NAME,
            column("stream_id"),
            column("version"),
            column("event_type"),
            column("payload"),
            column("metadata_json"),
            column("occurred_at"),
        )
        stmt = (
            select(t)
            .where(column("stream_id") == stream_id)
            .where(column("version") > from_version)
            .order_by(column("version"))
        )
        result = await self._session.execute(stmt)
        rows = result.fetchall()
        return [
            StoredEvent(
                stream_id=row.stream_id,
                version=row.version,
                event_type=row.event_type,
                payload=bytes(row.payload),
                metadata=json.loads(row.metadata_json) if row.metadata_json else {},
                occurred_at=row.occurred_at,
            )
            for row in rows
        ]


__all__ = ["SQLAlchemyEventStore"]
