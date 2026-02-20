"""Application event sourcing – EventStore Protocol and InMemoryEventStore."""

from __future__ import annotations

import abc
from typing import Any

from mp_commons.application.event_sourcing.stored_event import StoredEvent


class OptimisticConcurrencyError(Exception):
    """Raised when the expected stream version does not match the current one."""

    def __init__(self, stream_id: str, expected: int, actual: int) -> None:
        self.stream_id = stream_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Concurrency conflict on stream '{stream_id}': "
            f"expected version {expected}, found {actual}"
        )


class EventStore(abc.ABC):
    """Port — durable append-only event store.

    Implement with any persistence backend (PostgreSQL, EventStoreDB, …).
    ``expected_version`` is used for **optimistic concurrency control**:

    - Pass ``0`` when creating a new stream (no events exist yet).
    - Pass the current version (``len(events)``) when appending to an
      existing stream.
    - The store raises :class:`OptimisticConcurrencyError` if the stream's
      actual version differs from *expected_version*.
    """

    @abc.abstractmethod
    async def append(
        self,
        stream_id: str,
        events: list[StoredEvent],
        expected_version: int,
    ) -> None:
        """Append *events* to *stream_id*, enforcing optimistic locking."""

    @abc.abstractmethod
    async def load(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> list[StoredEvent]:
        """Return all events for *stream_id* with ``version > from_version``."""


class InMemoryEventStore(EventStore):
    """In-memory :class:`EventStore` for tests and local development.

    Raises :class:`OptimisticConcurrencyError` when *expected_version* does
    not match the current length of the stream.
    """

    def __init__(self) -> None:
        # stream_id → ordered list of StoredEvent
        self._streams: dict[str, list[StoredEvent]] = {}

    async def append(
        self,
        stream_id: str,
        events: list[StoredEvent],
        expected_version: int,
    ) -> None:
        stream = self._streams.setdefault(stream_id, [])
        actual_version = len(stream)
        if actual_version != expected_version:
            raise OptimisticConcurrencyError(stream_id, expected_version, actual_version)
        stream.extend(events)

    async def load(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> list[StoredEvent]:
        stream = self._streams.get(stream_id, [])
        return [e for e in stream if e.version > from_version]

    def stream_version(self, stream_id: str) -> int:
        """Return the current number of events in *stream_id*."""
        return len(self._streams.get(stream_id, []))

    def all_events(self, stream_id: str | None = None) -> list[StoredEvent]:
        """Return all stored events, optionally filtered by *stream_id*."""
        if stream_id is not None:
            return list(self._streams.get(stream_id, []))
        return [e for stream in self._streams.values() for e in stream]


__all__ = ["EventStore", "InMemoryEventStore", "OptimisticConcurrencyError"]
