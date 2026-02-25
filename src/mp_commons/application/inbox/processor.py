from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from mp_commons.application.inbox.store import InboxRecord, InboxStatus, InboxStore

__all__ = ["CommandBus", "InboxProcessor"]


class CommandBus(Protocol):
    async def dispatch(self, event_type: str, payload: Any) -> None: ...


class InboxProcessor:
    """Processes inbox records with exactly-once semantics."""

    def __init__(self, store: InboxStore, command_bus: CommandBus) -> None:
        self._store = store
        self._bus = command_bus

    async def process(self, record: InboxRecord) -> InboxRecord:
        # Duplicate check
        if await self._store.is_duplicate(record.id):
            record.status = InboxStatus.DUPLICATE
            await self._store.save(record)
            return record

        # Persist as pending first (idempotency anchor)
        await self._store.save(record)

        try:
            await self._bus.dispatch(record.event_type, record.payload)
            record.status = InboxStatus.PROCESSED
            record.processed_at = datetime.now(timezone.utc)
        except Exception as exc:  # noqa: BLE001
            record.status = InboxStatus.FAILED
            record.error = str(exc)

        await self._store.save(record)
        return record
