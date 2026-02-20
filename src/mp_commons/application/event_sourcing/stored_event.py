"""Application event sourcing – StoredEvent."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any


@dataclasses.dataclass(frozen=True)
class StoredEvent:
    """An event as persisted in the event store.

    ``payload`` is the serialised representation of the original domain event
    (e.g. JSON bytes).  ``metadata`` carries infrastructure-level concerns
    (correlation id, causation id, tenant id, …).
    """

    stream_id: str
    """Identifies the aggregate stream (e.g. ``"Order-<uuid>"``).

    By convention this is ``"<AggregateType>-<id>"``.
    """

    version: int
    """1-based, monotonically increasing sequence number within the stream."""

    event_type: str
    """Fully-qualified class name or logical name of the domain event."""

    payload: bytes
    """Serialised event data (JSON, MessagePack, protobuf, …)."""

    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)
    """Infrastructure metadata (correlation_id, tenant_id, …)."""

    occurred_at: datetime = dataclasses.field(
        default_factory=lambda: datetime.now(UTC)
    )
    """Wall-clock time when the event was recorded."""


__all__ = ["StoredEvent"]
