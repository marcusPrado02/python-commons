"""Application event sourcing – Projector abstract base class."""

from __future__ import annotations

import abc
from typing import Generic, TypeVar

from mp_commons.application.event_sourcing.stored_event import StoredEvent

E = TypeVar("E")


class Projector(Generic[E], abc.ABC):
    """Updates a read model by processing a stream of stored events.

    Subclass and implement :meth:`project` to handle each :class:`StoredEvent`.
    The type parameter *E* is the read-model entity type this projector produces.

    Example::

        class OrderSummaryProjector(Projector[OrderSummary]):
            def __init__(self) -> None:
                self.summaries: dict[str, OrderSummary] = {}

            async def project(self, event: StoredEvent) -> None:
                if event.event_type == "OrderPlaced":
                    payload = json.loads(event.payload)
                    self.summaries[event.stream_id] = OrderSummary(
                        order_id=payload["order_id"],
                        status="PLACED",
                    )
    """

    @abc.abstractmethod
    async def project(self, event: StoredEvent) -> None:
        """Process a single stored event and update the read model."""

    async def project_all(self, events: list[StoredEvent]) -> None:
        """Process a list of events in order."""
        for event in events:
            await self.project(event)


__all__ = ["Projector"]
