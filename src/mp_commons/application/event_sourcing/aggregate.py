"""Application event sourcing – EventSourcedAggregate base class."""

from __future__ import annotations

import abc

from mp_commons.application.event_sourcing.stored_event import StoredEvent
from mp_commons.kernel.ddd.aggregate import AggregateRoot
from mp_commons.kernel.types.ids import EntityId


class EventSourcedAggregate(AggregateRoot, abc.ABC):
    """Aggregate root that can reconstruct its state by replaying stored events.

    Subclasses must implement :meth:`apply_stored_event` to update their
    state for each event type.

    Example::

        class Order(EventSourcedAggregate):
            def __init__(self, id: EntityId) -> None:
                super().__init__(id)
                self.status: str = "PENDING"

            @classmethod
            def stream_prefix(cls) -> str:
                return "Order"

            def apply_stored_event(self, event: StoredEvent) -> None:
                if event.event_type == "OrderPlaced":
                    self.status = "PLACED"
                elif event.event_type == "OrderCancelled":
                    self.status = "CANCELLED"
    """

    @abc.abstractmethod
    def apply_stored_event(self, event: StoredEvent) -> None:
        """Update internal state from a single persisted event.

        Called during event replay — must **not** raise domain events.
        """

    @classmethod
    def stream_prefix(cls) -> str:
        """Prefix used to build the stream identifier (defaults to class name)."""
        return cls.__name__

    @classmethod
    def stream_id_for(cls, agg_id: EntityId) -> str:
        """Build the canonical stream id: ``"<Prefix>-<id>"``."""
        return f"{cls.stream_prefix()}-{agg_id}"


__all__ = ["EventSourcedAggregate"]
