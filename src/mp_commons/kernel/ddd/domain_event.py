"""Domain events and their envelopes."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclasses.dataclass(frozen=True)
class DomainEvent:
    """Base class for domain events.

    Subclasses should extend this and add their own payload fields.

    Example::

        @dataclasses.dataclass(frozen=True)
        class OrderPlaced(DomainEvent):
            order_id: str
            total_amount: Money
    """

    event_id: str = dataclasses.field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = dataclasses.field(
        default_factory=lambda: datetime.now(UTC)
    )

    @property
    def event_type(self) -> str:
        return type(self).__name__


@dataclasses.dataclass(frozen=True)
class DomainEventEnvelope:
    """Wraps a ``DomainEvent`` with routing & metadata for the message bus."""

    event: DomainEvent
    aggregate_id: str
    aggregate_type: str
    sequence: int
    tenant_id: str | None = None
    correlation_id: str | None = None
    schema_version: int = 1
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def event_type(self) -> str:
        return self.event.event_type


@dataclasses.dataclass(frozen=True)
class EventSourcingSnapshot:
    """Periodic state snapshot for event-sourced aggregates."""

    aggregate_id: str
    aggregate_type: str
    sequence: int
    state: dict[str, Any]
    taken_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))
    schema_version: int = 1


__all__ = ["DomainEvent", "DomainEventEnvelope", "EventSourcingSnapshot"]
