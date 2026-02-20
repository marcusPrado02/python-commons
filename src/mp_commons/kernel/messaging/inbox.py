"""Kernel messaging – inbox pattern ports."""
from __future__ import annotations

import abc
import dataclasses
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


class InboxStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


@dataclasses.dataclass
class InboxRecord:
    """Transactional inbox record for exactly-once processing."""

    id: str = dataclasses.field(default_factory=lambda: str(uuid4()))
    message_id: str = ""
    topic: str = ""
    payload: bytes = b""
    headers: dict[str, str] = dataclasses.field(default_factory=dict)
    status: InboxStatus = InboxStatus.RECEIVED
    received_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None
    consumer_group: str = ""
    error: str | None = None


class InboxRepository(abc.ABC):
    """Port: persistence for inbox records."""

    @abc.abstractmethod
    async def save(self, record: InboxRecord) -> None: ...

    @abc.abstractmethod
    async def find_by_message_id(self, message_id: str) -> InboxRecord | None: ...

    @abc.abstractmethod
    async def mark_processed(self, record_id: str) -> None: ...

    @abc.abstractmethod
    async def mark_failed(self, record_id: str, error: str) -> None: ...


class InboxStore(abc.ABC):
    """Simplified inbox port — idempotent record + duplicate check.

    Lighter-weight alternative to ``InboxRepository`` for cases where
    only deduplication matters (not full record lifecycle).
    """

    @abc.abstractmethod
    async def record(self, message_id: str) -> None:
        """Persist *message_id* as processed."""
        ...

    @abc.abstractmethod
    async def has_been_processed(self, message_id: str) -> bool:
        """Return ``True`` if *message_id* was already recorded."""
        ...


__all__ = [
    "InboxRecord",
    "InboxRepository",
    "InboxStatus",
    "InboxStore",
]
