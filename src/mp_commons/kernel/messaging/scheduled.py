"""Kernel messaging – scheduled / delayed message ports."""
from __future__ import annotations

import abc
import dataclasses
from datetime import UTC, datetime
from uuid import uuid4


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScheduledMessage:
    """A message that should be delivered at a specific future time.

    Example::

        msg = ScheduledMessage(
            topic="orders.reminders",
            payload=b'{"order_id": "x"}',
            deliver_at=datetime.now(UTC) + timedelta(hours=1),
        )
    """

    id: str = dataclasses.field(default_factory=lambda: str(uuid4()))
    topic: str = ""
    payload: bytes = b""
    headers: dict[str, str] = dataclasses.field(default_factory=dict)
    deliver_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))


class ScheduledMessageStore(abc.ABC):
    """Port: schedule messages for future delivery."""

    @abc.abstractmethod
    async def schedule(self, message: ScheduledMessage) -> None:
        """Persist *message* so it is delivered at ``message.deliver_at``."""
        ...

    @abc.abstractmethod
    async def due(self, now: datetime, limit: int = 100) -> list[ScheduledMessage]:
        """Return messages whose ``deliver_at`` is <= *now* (oldest first)."""
        ...

    @abc.abstractmethod
    async def delete(self, message_id: str) -> None:
        """Remove a scheduled message (after it has been delivered)."""
        ...


__all__ = ["ScheduledMessage", "ScheduledMessageStore"]
