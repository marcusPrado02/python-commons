"""Testing fakes – InMemoryOutboxRepository."""
from __future__ import annotations

from mp_commons.kernel.messaging import OutboxRecord, OutboxRepository, OutboxStatus


class InMemoryOutboxRepository(OutboxRepository):
    """Dict-backed outbox repository for tests."""

    def __init__(self) -> None:
        self._records: dict[str, OutboxRecord] = {}

    async def save(self, record: OutboxRecord) -> None:
        self._records[record.id] = record

    async def get_pending(self, limit: int = 100) -> list[OutboxRecord]:
        pending = [r for r in self._records.values() if r.status == OutboxStatus.PENDING]
        return pending[:limit]

    async def mark_dispatched(self, record_id: str) -> None:
        if record_id in self._records:
            r = self._records[record_id]
            self._records[record_id] = OutboxRecord(
                id=r.id, aggregate_id=r.aggregate_id, aggregate_type=r.aggregate_type,
                event_type=r.event_type, topic=r.topic, payload=r.payload,
                headers=r.headers, status=OutboxStatus.DISPATCHED, created_at=r.created_at,
            )

    async def mark_failed(self, record_id: str, error: str) -> None:
        if record_id in self._records:
            r = self._records[record_id]
            self._records[record_id] = OutboxRecord(
                id=r.id, aggregate_id=r.aggregate_id, aggregate_type=r.aggregate_type,
                event_type=r.event_type, topic=r.topic, payload=r.payload,
                headers=r.headers, status=OutboxStatus.FAILED, created_at=r.created_at,
            )

    def all_records(self) -> list[OutboxRecord]:
        return list(self._records.values())


__all__ = ["InMemoryOutboxRepository"]
