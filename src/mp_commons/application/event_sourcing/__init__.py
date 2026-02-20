"""Application — Event Sourcing."""

from mp_commons.application.event_sourcing.aggregate import EventSourcedAggregate
from mp_commons.application.event_sourcing.projector import Projector
from mp_commons.application.event_sourcing.repository import EventSourcedRepository
from mp_commons.application.event_sourcing.snapshot import (
    InMemorySnapshotStore,
    SnapshotRecord,
    SnapshotStore,
)
from mp_commons.application.event_sourcing.store import (
    EventStore,
    InMemoryEventStore,
    OptimisticConcurrencyError,
)
from mp_commons.application.event_sourcing.stored_event import StoredEvent

__all__ = [
    "EventSourcedAggregate",
    "EventSourcedRepository",
    "EventStore",
    "InMemoryEventStore",
    "InMemorySnapshotStore",
    "OptimisticConcurrencyError",
    "Projector",
    "SnapshotRecord",
    "SnapshotStore",
    "StoredEvent",
]
