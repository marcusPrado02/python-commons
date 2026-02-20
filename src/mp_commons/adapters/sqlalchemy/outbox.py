"""SQLAlchemy adapter – SqlAlchemyOutboxRepository."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mp_commons.kernel.messaging import OutboxRecord, OutboxRepository, OutboxStatus


class SqlAlchemyOutboxRepository(OutboxRepository):
    """SQLAlchemy-backed outbox repository."""

    def __init__(self, session: Any, model: Any | None = None) -> None:
        self._session = session
        self._model = model

    async def save(self, record: OutboxRecord) -> None:
        if self._model is None:
            raise RuntimeError("OutboxRecordModel not configured")
        self._session.add(self._model(**self._record_to_dict(record)))

    async def get_pending(self, limit: int = 100) -> list[OutboxRecord]:
        if self._model is None:
            raise RuntimeError("OutboxRecordModel not configured")
        from sqlalchemy import select  # type: ignore[import-untyped]
        result = await self._session.execute(
            select(self._model).where(self._model.status == OutboxStatus.PENDING.value).limit(limit)
        )
        return [self._row_to_record(row) for row in result.scalars().all()]

    async def mark_dispatched(self, record_id: str) -> None:
        await self._update(record_id, {"status": OutboxStatus.DISPATCHED.value, "dispatched_at": datetime.now(UTC)})

    async def mark_failed(self, record_id: str, error: str) -> None:
        await self._update(record_id, {"status": OutboxStatus.FAILED.value, "last_error": error})

    async def _update(self, record_id: str, values: dict[str, Any]) -> None:
        from sqlalchemy import update  # type: ignore[import-untyped]
        await self._session.execute(update(self._model).where(self._model.id == record_id).values(**values))

    def _record_to_dict(self, record: OutboxRecord) -> dict[str, Any]:
        return {
            "id": record.id, "aggregate_id": record.aggregate_id,
            "aggregate_type": record.aggregate_type, "event_type": record.event_type,
            "topic": record.topic, "payload": record.payload, "headers": record.headers,
            "status": record.status.value, "created_at": record.created_at,
        }

    def _row_to_record(self, row: Any) -> OutboxRecord:
        return OutboxRecord(
            id=row.id, aggregate_id=row.aggregate_id, aggregate_type=row.aggregate_type,
            event_type=row.event_type, topic=row.topic, payload=row.payload,
            headers=row.headers or {}, status=OutboxStatus(row.status), created_at=row.created_at,
        )


__all__ = ["SqlAlchemyOutboxRepository"]
