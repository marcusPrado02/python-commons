"""Testing fakes – InMemoryInboxRepository."""
from __future__ import annotations

from mp_commons.kernel.messaging import InboxRecord, InboxRepository, InboxStatus


class InMemoryInboxRepository(InboxRepository):
    """Dict-backed inbox repository for tests."""

    def __init__(self) -> None:
        self._records: dict[str, InboxRecord] = {}

    async def save(self, record: InboxRecord) -> None:
        self._records[record.message_id] = record

    async def find_by_message_id(self, message_id: str) -> InboxRecord | None:
        return self._records.get(message_id)

    # Keep the old ``get`` alias for backwards compat
    async def get(self, message_id: str) -> InboxRecord | None:
        return self._records.get(message_id)

    async def mark_processed(self, message_id: str) -> None:
        if message_id in self._records:
            r = self._records[message_id]
            self._records[message_id] = InboxRecord(
                id=r.id,
                message_id=r.message_id,
                topic=r.topic,
                payload=r.payload,
                headers=r.headers,
                status=InboxStatus.PROCESSED,
                received_at=r.received_at,
                processed_at=r.processed_at,
                consumer_group=r.consumer_group,
                error=r.error,
            )

    async def mark_failed(self, message_id: str, error: str) -> None:
        if message_id in self._records:
            r = self._records[message_id]
            self._records[message_id] = InboxRecord(
                id=r.id,
                message_id=r.message_id,
                topic=r.topic,
                payload=r.payload,
                headers=r.headers,
                status=InboxStatus.FAILED,
                received_at=r.received_at,
                processed_at=r.processed_at,
                consumer_group=r.consumer_group,
                error=error,
            )

    def all_records(self) -> list[InboxRecord]:
        return list(self._records.values())


__all__ = ["InMemoryInboxRepository"]
