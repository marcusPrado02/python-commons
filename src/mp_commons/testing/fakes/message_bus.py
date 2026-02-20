"""Testing fakes – InMemoryMessageBus."""
from __future__ import annotations

from typing import Any

from mp_commons.kernel.messaging import Message, MessageBus


class InMemoryMessageBus(MessageBus):
    """In-memory message bus for tests."""

    def __init__(self) -> None:
        self._messages: list[Message[Any]] = []

    async def publish(self, message: Message[Any]) -> None:
        self._messages.append(message)

    async def publish_batch(self, messages: list[Message[Any]]) -> None:
        self._messages.extend(messages)

    @property
    def published(self) -> list[Message[Any]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    def of_topic(self, topic: str) -> list[Message[Any]]:
        return [m for m in self._messages if m.topic == topic]


__all__ = ["InMemoryMessageBus"]
