"""Kernel messaging – dead-letter queue port."""
from __future__ import annotations

import abc
import dataclasses
from datetime import UTC, datetime
from uuid import uuid4


@dataclasses.dataclass
class DeadLetterEntry:
    """A message that could not be processed after all retries."""

    id: str = dataclasses.field(default_factory=lambda: str(uuid4()))
    message_id: str = ""
    topic: str = ""
    payload: bytes = b""
    headers: dict[str, str] = dataclasses.field(default_factory=dict)
    reason: str = ""
    failed_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))
    retry_count: int = 0
    replayed: bool = False


class DeadLetterStore(abc.ABC):
    """Port: persistence and replay for dead-lettered messages."""

    @abc.abstractmethod
    async def push(self, message_id: str, payload: bytes, reason: str) -> None:
        """Persist a failed message with its failure *reason*."""
        ...

    @abc.abstractmethod
    async def list(self, limit: int = 100) -> list[DeadLetterEntry]:
        """Return at most *limit* dead-letter entries (oldest first)."""
        ...

    @abc.abstractmethod
    async def replay(self, entry_id: str) -> None:
        """Re-enqueue the message identified by *entry_id* for reprocessing."""
        ...


__all__ = ["DeadLetterEntry", "DeadLetterStore"]
