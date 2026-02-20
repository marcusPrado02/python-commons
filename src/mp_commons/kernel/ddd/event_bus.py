"""DomainEventBus port — in-process event pub/sub."""

from __future__ import annotations

from typing import Any, Callable, Coroutine, Protocol

from mp_commons.kernel.ddd.domain_event import DomainEvent

#: Type alias for an async event handler function.
Handler = Callable[[DomainEvent], Coroutine[Any, Any, None]]


class DomainEventBus(Protocol):
    """Port: in-process domain event bus.

    Application services publish events; handlers (registered by bootstrap
    or test setup) react to them.  Concrete implementations may be
    synchronous (in-memory) or delegate to an async message broker.

    Example::

        bus = InMemoryEventBus()
        await bus.subscribe(OrderPlaced, send_confirmation_email)
        await bus.publish(OrderPlaced(order_id="x"))
    """

    async def publish(self, event: DomainEvent) -> None:
        """Broadcast *event* to all registered handlers for its type."""
        ...

    async def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Handler,
    ) -> None:
        """Register *handler* to be called when *event_type* is published."""
        ...


__all__ = ["DomainEventBus", "Handler"]
