"""Application notifications – push notification models and protocol."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

__all__ = [
    "InMemoryPushSender",
    "PushNotification",
    "PushNotificationSender",
    "SendResult",
]


@dataclass
class PushNotification:
    """A mobile push notification payload."""

    device_tokens: list[str]
    title: str
    body: str
    data: dict = field(default_factory=dict)
    badge: int | None = None
    sound: str | None = None


@dataclass(frozen=True)
class SendResult:
    """The delivery result for a single device token."""

    token: str
    success: bool
    error: str | None = None


@runtime_checkable
class PushNotificationSender(Protocol):
    """Port: send push notifications to mobile devices."""

    async def send(self, notification: PushNotification) -> list[SendResult]: ...


class InMemoryPushSender:
    """Fake PushNotificationSender that captures sent notifications."""

    def __init__(self) -> None:
        self.sent: list[PushNotification] = []

    async def send(self, notification: PushNotification) -> list[SendResult]:
        self.sent.append(notification)
        return [SendResult(token=t, success=True) for t in notification.device_tokens]

    def reset(self) -> None:
        self.sent.clear()

    @property
    def count(self) -> int:
        return len(self.sent)
