"""OutboxPublisher port — decouples aggregates from message transport."""

from __future__ import annotations

from typing import Protocol

from mp_commons.kernel.ddd.domain_event import DomainEvent


class OutboxPublisher(Protocol):
    """Port: persists pending domain events to the transactional outbox.

    Concrete implementations (e.g. SQLAlchemy, in-memory fake) live in the
    adapter layer and are injected into application services.

    Example::

        class SqlOutboxPublisher:
            async def publish_events(self, events: list[DomainEvent]) -> None:
                for event in events:
                    await session.execute(insert(OutboxTable).values(...))
    """

    async def publish_events(self, events: list[DomainEvent]) -> None:
        """Persist *events* to the outbox within the current transaction."""
        ...


__all__ = ["OutboxPublisher"]
