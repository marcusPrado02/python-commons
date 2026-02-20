"""Kernel messaging – message primitives and bus ports."""
from __future__ import annotations

import abc
import dataclasses
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar
from uuid import uuid4

T = TypeVar("T")

type EventName = str
type EventVersion = int
type MessageId = str


@dataclasses.dataclass(frozen=True)
class MessageHeaders:
    """Envelope metadata propagated with every message."""

    correlation_id: str | None = None
    tenant_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None
    content_type: str = "application/json"
    schema_version: int = 1
    extra: dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class Message(Generic[T]):
    """Transport-agnostic message envelope."""

    id: MessageId = dataclasses.field(default_factory=lambda: str(uuid4()))
    topic: str = ""
    payload: T | None = None
    headers: MessageHeaders = dataclasses.field(default_factory=MessageHeaders)
    occurred_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))


class MessageSerializer(abc.ABC, Generic[T]):
    """Port: serialize / deserialize message payloads."""

    @abc.abstractmethod
    def serialize(self, payload: T) -> bytes: ...

    @abc.abstractmethod
    def deserialize(self, data: bytes, target_type: type[T]) -> T: ...


class MessageBus(abc.ABC):
    """Port: publish messages to a transport (Kafka, NATS, Redis Streams…)."""

    @abc.abstractmethod
    async def publish(self, message: Message[Any]) -> None: ...

    @abc.abstractmethod
    async def publish_batch(self, messages: list[Message[Any]]) -> None: ...


class EventPublisher(abc.ABC):
    """Port: domain-event publisher with routing by event type."""

    @abc.abstractmethod
    async def publish(self, topic: str, payload: Any, headers: MessageHeaders | None = None) -> None: ...


class EventConsumer(abc.ABC):
    """Port: subscribe to domain events."""

    @abc.abstractmethod
    async def subscribe(self, topic: str) -> None: ...

    @abc.abstractmethod
    async def start(self) -> None: ...

    @abc.abstractmethod
    async def stop(self) -> None: ...


__all__ = [
    "EventConsumer",
    "EventName",
    "EventPublisher",
    "EventVersion",
    "Message",
    "MessageBus",
    "MessageHeaders",
    "MessageId",
    "MessageSerializer",
]
