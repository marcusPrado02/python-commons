"""AggregateRoot — owns domain events and enforces invariants."""

from __future__ import annotations

from mp_commons.kernel.ddd.domain_event import DomainEvent
from mp_commons.kernel.ddd.entity import Entity
from mp_commons.kernel.types.ids import EntityId


class AggregateRoot(Entity):
    """Aggregate root — owns domain events and enforces invariants."""

    _version: int
    _events: list[DomainEvent]

    def __init__(self, id: EntityId) -> None:  # noqa: A002
        super().__init__(id)
        self._version = 0
        self._events = []

    def _raise_event(self, event: DomainEvent) -> None:
        """Record a domain event and bump the version."""
        self._events.append(event)
        self._version += 1

    def pull_events(self) -> list[DomainEvent]:
        """Return and clear pending domain events (canonical name)."""
        events = list(self._events)
        self._events.clear()
        return events

    def collect_events(self) -> list[DomainEvent]:
        """Alias for :meth:`pull_events` for backwards compatibility."""
        return self.pull_events()

    @property
    def version(self) -> int:
        return self._version

    def _check_invariants(self) -> None:
        """Override to run invariant assertions after state changes."""


__all__ = ["AggregateRoot"]
