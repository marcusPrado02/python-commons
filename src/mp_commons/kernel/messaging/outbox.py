"""Kernel messaging – outbox pattern ports."""
from __future__ import annotations

import abc
import dataclasses
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


class OutboxStatus(str, Enum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    FAILED = "FAILED"


@dataclasses.dataclass
class OutboxRecord:
    """Transactional outbox record stored alongside business data."""

    id: str = dataclasses.field(default_factory=lambda: str(uuid4()))
    aggregate_id: str = ""
    aggregate_type: str = ""
    event_type: str = ""
    topic: str = ""
    payload: bytes = b""
    headers: dict[str, str] = dataclasses.field(default_factory=dict)
    status: OutboxStatus = OutboxStatus.PENDING
    created_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))
    dispatched_at: datetime | None = None
    retry_count: int = 0
    last_error: str | None = None


class OutboxRepository(abc.ABC):
    """Port: persistence for outbox records."""

    @abc.abstractmethod
    async def save(self, record: OutboxRecord) -> None: ...

    @abc.abstractmethod
    async def get_pending(self, limit: int = 100) -> list[OutboxRecord]: ...

    @abc.abstractmethod
    async def mark_dispatched(self, record_id: str) -> None: ...

    @abc.abstractmethod
    async def mark_failed(self, record_id: str, error: str) -> None: ...


class OutboxDispatcher(abc.ABC):
    """Port: reads pending outbox records and publishes them."""

    @abc.abstractmethod
    async def dispatch_pending(self) -> int: ...


__all__ = [
    "OutboxDispatcher",
    "OutboxRecord",
    "OutboxRepository",
    "OutboxStatus",
]
