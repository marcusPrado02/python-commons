"""Application event sourcing – EventSourcedRepository."""

from __future__ import annotations

import abc
import json
from typing import Any, Callable, Generic, TypeVar

from mp_commons.application.event_sourcing.aggregate import EventSourcedAggregate
from mp_commons.application.event_sourcing.store import EventStore
from mp_commons.application.event_sourcing.stored_event import StoredEvent
from mp_commons.kernel.ddd.domain_event import DomainEvent
from mp_commons.kernel.types.ids import EntityId

T = TypeVar("T", bound=EventSourcedAggregate)
TId = TypeVar("TId", bound=EntityId)


def _default_serialise(event: DomainEvent) -> bytes:
    """Serialise a domain event to JSON bytes (best-effort)."""
    data: dict[str, Any] = {}
    for key, val in vars(event).items():
        try:
            json.dumps(val)
            data[key] = val
        except (TypeError, ValueError):
            data[key] = str(val)
    return json.dumps(data).encode()


class EventSourcedRepository(Generic[T, TId], abc.ABC):
    """Generic repository for event-sourced aggregates.

    Subclasses must implement :meth:`_aggregate_class` and
    :meth:`_create_empty`.

    Example::

        class OrderRepository(EventSourcedRepository[Order, EntityId]):
            def _aggregate_class(self) -> type[Order]:
                return Order

            def _create_empty(self, agg_id: EntityId) -> Order:
                return Order(agg_id)

        repo = OrderRepository(store=event_store)
        order = await repo.load(order_id)
        order.place(...)
        await repo.save(order)
    """

    def __init__(
        self,
        store: EventStore,
        serialise: Callable[[DomainEvent], bytes] | None = None,
        metadata_factory: Callable[[DomainEvent], dict[str, Any]] | None = None,
    ) -> None:
        self._store = store
        self._serialise = serialise or _default_serialise
        self._metadata_factory = metadata_factory or (lambda _: {})

    @abc.abstractmethod
    def _aggregate_class(self) -> type[T]:
        """Return the concrete aggregate type (for stream-id construction)."""

    @abc.abstractmethod
    def _create_empty(self, agg_id: TId) -> T:
        """Return a blank aggregate instance with *agg_id*."""

    async def load(self, agg_id: TId) -> T | None:
        """Replay stored events; returns ``None`` if stream is empty."""
        cls = self._aggregate_class()
        stream_id = cls.stream_id_for(agg_id)  # type: ignore[arg-type]
        events = await self._store.load(stream_id)
        if not events:
            return None
        agg = self._create_empty(agg_id)
        for event in events:
            agg.apply_stored_event(event)
            agg._version = event.version  # noqa: SLF001
        return agg

    async def save(self, agg: T) -> None:
        """Append pending domain events to the event store."""
        domain_events = agg.pull_events()
        if not domain_events:
            return

        cls = self._aggregate_class()
        stream_id = cls.stream_id_for(agg.id)  # type: ignore[arg-type]

        n = len(domain_events)
        prior_version = agg.version - n

        stored = [
            StoredEvent(
                stream_id=stream_id,
                version=prior_version + i + 1,
                event_type=de.event_type,
                payload=self._serialise(de),
                metadata=self._metadata_factory(de),
                occurred_at=de.occurred_at,
            )
            for i, de in enumerate(domain_events)
        ]

        await self._store.append(stream_id, stored, expected_version=prior_version)


__all__ = ["EventSourcedRepository"]
