from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol
import uuid

__all__ = [
    "InboxRecord",
    "InboxStatus",
    "InboxStore",
    "InMemoryInboxStore",
]


class InboxStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"


@dataclass
class InboxRecord:
    """Persisted inbound event for at-least-once / exactly-once processing."""

    source: str
    event_type: str
    payload: Any
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime | None = None
    status: InboxStatus = InboxStatus.PENDING
    error: str | None = None


class InboxStore(Protocol):
    async def save(self, record: InboxRecord) -> None: ...
    async def load(self, record_id: str) -> InboxRecord | None: ...
    async def is_duplicate(self, record_id: str) -> bool: ...


class InMemoryInboxStore:
    def __init__(self) -> None:
        self._records: dict[str, InboxRecord] = {}

    async def save(self, record: InboxRecord) -> None:
        self._records[record.id] = record

    async def load(self, record_id: str) -> InboxRecord | None:
        return self._records.get(record_id)

    async def is_duplicate(self, record_id: str) -> bool:
        rec = self._records.get(record_id)
        return rec is not None and rec.status == InboxStatus.PROCESSED
