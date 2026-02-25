"""Application email – EmailSender Protocol (port)."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from mp_commons.application.email.message import EmailMessage

__all__ = ["EmailSender"]


@runtime_checkable
class EmailSender(Protocol):
    """Port: send transactional email messages."""

    async def send(self, message: EmailMessage) -> str:
        """Send a single message; returns an opaque message-id string."""
        ...

    async def send_bulk(self, messages: list[EmailMessage]) -> list[str]:
        """Send multiple messages; returns list of message-ids in order."""
        ...
