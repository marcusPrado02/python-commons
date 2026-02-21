"""SQLAlchemy adapter — SQLAlchemyAuditStore."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from mp_commons.kernel.security.audit import AuditEvent, AuditStore
from mp_commons.kernel.types.ids import EntityId


class SQLAlchemyAuditStore(AuditStore):
    """SQLAlchemy 2.x Core-based audit store.

    Uses the ``audit_events`` table; create it with
    :meth:`create_table`.  The implementation uses raw Core
    ``insert``/``select`` so callers do **not** need to declare an ORM
    model — only an :class:`~sqlalchemy.ext.asyncio.AsyncSession` (or a
    plain async-capable session/connection) is required.

    Recommended indexes (created by :meth:`create_indexes`):
    - ``(principal_id, occurred_at)`` — for per-principal timeline queries
    - ``action`` — for action-filter queries
    """

    TABLE_NAME = "audit_events"

    def __init__(self, session: Any) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    @classmethod
    async def create_table(cls, bind: Any) -> None:
        """Create the ``audit_events`` table if it does not exist.

        *bind* should be an
        :class:`~sqlalchemy.ext.asyncio.AsyncEngine` or a synchronous
        :class:`~sqlalchemy.engine.Engine`.
        """
        from sqlalchemy import (  # type: ignore[import-untyped]
            Column,
            DateTime,
            LargeBinary,
            MetaData,
            String,
            Table,
            Text,
        )

        meta = MetaData()
        table = Table(
            cls.TABLE_NAME,
            meta,
            Column("event_id", String(128), primary_key=True),
            Column("principal_id", String(256), nullable=False, index=True),
            Column("action", String(256), nullable=False, index=True),
            Column("resource_type", String(256), nullable=False),
            Column("resource_id", String(256), nullable=False),
            Column("outcome", String(8), nullable=False),
            Column("occurred_at", DateTime(timezone=True), nullable=False, index=True),
            Column("metadata_json", Text, nullable=False, default="{}"),
        )
        try:
            # SQLAlchemy 2.x AsyncEngine path
            async with bind.begin() as conn:
                await conn.run_sync(meta.create_all)
        except AttributeError:
            # sync Engine fallback
            meta.create_all(bind)

    @classmethod
    async def create_indexes(cls, bind: Any) -> None:
        """Create recommended composite indexes.

        Idempotent via ``IF NOT EXISTS``; delegates to
        :meth:`create_table` which already creates single-column indexes.
        Composite index on ``(principal_id, occurred_at)`` is added here.
        """
        from sqlalchemy import text  # type: ignore[import-untyped]

        sql = text(
            f"CREATE INDEX IF NOT EXISTS idx_audit_principal_time "
            f"ON {cls.TABLE_NAME} (principal_id, occurred_at)"
        )
        try:
            async with bind.begin() as conn:
                await conn.execute(sql)
        except AttributeError:
            with bind.begin() as conn:
                conn.execute(sql)

    # ------------------------------------------------------------------
    # AuditStore interface
    # ------------------------------------------------------------------

    async def record(self, event: AuditEvent) -> None:
        import json

        from sqlalchemy import insert, table, column  # type: ignore[import-untyped]

        t = table(
            self.TABLE_NAME,
            column("event_id"),
            column("principal_id"),
            column("action"),
            column("resource_type"),
            column("resource_id"),
            column("outcome"),
            column("occurred_at"),
            column("metadata_json"),
        )
        stmt = insert(t).values(
            event_id=str(event.event_id),
            principal_id=event.principal_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            outcome=event.outcome,
            occurred_at=event.occurred_at,
            metadata_json=json.dumps(event.metadata),
        )
        await self._session.execute(stmt)

    async def query(
        self,
        *,
        principal_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        action_filter: str | None = None,
        outcome: Literal["allow", "deny"] | None = None,
        limit: int = 1000,
    ) -> list[AuditEvent]:
        import json

        from sqlalchemy import select, text, table, column  # type: ignore[import-untyped]

        t = table(
            self.TABLE_NAME,
            column("event_id"),
            column("principal_id"),
            column("action"),
            column("resource_type"),
            column("resource_id"),
            column("outcome"),
            column("occurred_at"),
            column("metadata_json"),
        )

        stmt = select(t).order_by(column("occurred_at")).limit(limit)

        if principal_id is not None:
            stmt = stmt.where(column("principal_id") == principal_id)
        if from_dt is not None:
            stmt = stmt.where(column("occurred_at") >= from_dt)
        if to_dt is not None:
            stmt = stmt.where(column("occurred_at") <= to_dt)
        if action_filter is not None:
            stmt = stmt.where(column("action").contains(action_filter))
        if outcome is not None:
            stmt = stmt.where(column("outcome") == outcome)

        result = await self._session.execute(stmt)
        rows = result.fetchall()
        return [
            AuditEvent(
                event_id=EntityId(row.event_id),
                principal_id=row.principal_id,
                action=row.action,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                outcome=row.outcome,
                occurred_at=row.occurred_at,
                metadata=json.loads(row.metadata_json) if row.metadata_json else {},
            )
            for row in rows
        ]


__all__ = ["SQLAlchemyAuditStore"]
