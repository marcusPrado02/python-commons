"""Application event sourcing – SnapshotStore Protocol."""

from __future__ import annotations

import abc
import dataclasses
from datetime import UTC, datetime


@dataclasses.dataclass
class SnapshotRecord:
    """A single snapshot entry."""

    stream_id: str
    version: int
    state_bytes: bytes
    taken_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))


class SnapshotStore(abc.ABC):
    """Port — store and retrieve aggregate state snapshots.

    Snapshots reduce event replay time for long-lived streams.
    """

    @abc.abstractmethod
    async def take(
        self,
        stream_id: str,
        version: int,
        state_bytes: bytes,
    ) -> None:
        """Persist a snapshot of *stream_id* at *version*."""

    @abc.abstractmethod
    async def latest(self, stream_id: str) -> SnapshotRecord | None:
        """Return the most recent snapshot for *stream_id*, or ``None``."""


class InMemorySnapshotStore(SnapshotStore):
    """In-memory :class:`SnapshotStore` for tests and local development."""

    def __init__(self) -> None:
        self._snapshots: dict[str, SnapshotRecord] = {}

    async def take(self, stream_id: str, version: int, state_bytes: bytes) -> None:
        self._snapshots[stream_id] = SnapshotRecord(
            stream_id=stream_id,
            version=version,
            state_bytes=state_bytes,
        )

    async def latest(self, stream_id: str) -> SnapshotRecord | None:
        return self._snapshots.get(stream_id)

    def all_snapshots(self) -> dict[str, SnapshotRecord]:
        return dict(self._snapshots)


__all__ = ["InMemorySnapshotStore", "SnapshotRecord", "SnapshotStore"]
