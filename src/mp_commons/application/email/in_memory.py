"""Application email – InMemoryEmailSender for unit tests."""
from __future__ import annotations

import uuid
from typing import Any

from mp_commons.application.email.message import EmailMessage

__all__ = ["InMemoryEmailSender"]


class InMemoryEmailSender:
    """Fake EmailSender that captures sent messages in memory."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self._ids: list[str] = []

    async def send(self, message: EmailMessage) -> str:
        self.sent.append(message)
        msg_id = str(uuid.uuid4())
        self._ids.append(msg_id)
        return msg_id

    async def send_bulk(self, messages: list[EmailMessage]) -> list[str]:
        return [await self.send(m) for m in messages]

    def reset(self) -> None:
        """Clear the outbox."""
        self.sent.clear()
        self._ids.clear()

    # convenience helpers
    @property
    def count(self) -> int:
        return len(self.sent)

    def last(self) -> EmailMessage | None:
        return self.sent[-1] if self.sent else None
