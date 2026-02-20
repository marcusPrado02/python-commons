"""Application CQRS – EventHandler, EventBus, InProcessEventBus."""

from __future__ import annotations

import abc
import asyncio
from typing import Any, Generic, TypeVar

from mp_commons.kernel.ddd.domain_event import DomainEvent

E = TypeVar("E", bound=DomainEvent)


class EventHandler(abc.ABC, Generic[E]):
    """Handle a single domain event type."""

    @abc.abstractmethod
    async def handle(self, event: E) -> None: ...


class EventBus(abc.ABC):
    """Port: publish domain events to all registered handlers."""

    @abc.abstractmethod
    def register(
        self, event_type: type[DomainEvent], handler: EventHandler[Any]
    ) -> None: ...

    @abc.abstractmethod
    async def publish(self, event: DomainEvent) -> None: ...


class InProcessEventBus(EventBus):
    """In-process event bus with fan-out via :func:`asyncio.gather`."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler[Any]]] = {}

    def register(
        self, event_type: type[DomainEvent], handler: EventHandler[Any]
    ) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        handlers = self._handlers.get(type(event), [])
        if handlers:
            await asyncio.gather(*(h.handle(event) for h in handlers))


__all__ = ["EventBus", "EventHandler", "InProcessEventBus"]
