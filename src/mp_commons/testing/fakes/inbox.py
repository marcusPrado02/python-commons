"""Testing fakes – InMemoryInboxRepository."""
from __future__ import annotations

from mp_commons.kernel.messaging import InboxRecord, InboxRepository, InboxStatus


class InMemoryInboxRepository(InboxRepository):
    """Dict-backed inbox repository for tests."""

    def __init__(self) -> None:
        self._records: dict[str, InboxRecord] = {}

    async def save(self, record: InboxRecord) -> None:
        self._records[record.message_id] = record

    async def get(self, message_id: str) -> InboxRecord | None:
        return self._records.get(message_id)

    async def mark_processed(self, message_id: str) -> None:
        if message_id in self._records:
            r = self._records[message_id]
            self._records[message_id] = InboxRecord(
                message_id=r.message_id, consumer_group=r.consumer_group,
                status=InboxStatus.PROCESSED, received_at=r.received_at,
            )

    def all_records(self) -> list[InboxRecord]:
        return list(self._records.values())


__all__ = ["InMemoryInboxRepository"]
