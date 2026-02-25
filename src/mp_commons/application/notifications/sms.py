"""Application notifications – SMS models and protocol."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "InMemorySmsSender",
    "SmsMessage",
    "SmsSender",
]


@dataclass(frozen=True)
class SmsMessage:
    """An outbound SMS message."""

    to: str  # E.164 format recommended, e.g. +15551234567
    body: str
    sender_id: str | None = None  # alphanumeric sender or number


@runtime_checkable
class SmsSender(Protocol):
    """Port: send SMS messages."""

    async def send(self, message: SmsMessage) -> str:
        """Send an SMS; returns provider message-id."""
        ...


class InMemorySmsSender:
    """Fake SmsSender that captures sent messages in memory."""

    def __init__(self) -> None:
        self.sent: list[SmsMessage] = []

    async def send(self, message: SmsMessage) -> str:
        self.sent.append(message)
        return f"mem-sms-{len(self.sent)}"

    def reset(self) -> None:
        self.sent.clear()

    @property
    def count(self) -> int:
        return len(self.sent)

    def last(self) -> SmsMessage | None:
        return self.sent[-1] if self.sent else None
