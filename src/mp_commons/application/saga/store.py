"""Application saga – SagaStore Protocol and InMemorySagaStore."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from mp_commons.application.saga.state import SagaState


@dataclass
class SagaRecord:
    """Durable representation of a saga's progress."""

    saga_id: str
    state: SagaState
    step_index: int
    ctx_snapshot: dict[str, Any] = field(default_factory=dict)


class SagaStore(abc.ABC):
    """Port — persist and retrieve saga progress.

    Implement this with any durable backend (SQL, Redis, …).
    """

    @abc.abstractmethod
    async def save(
        self,
        saga_id: str,
        state: SagaState,
        step_index: int,
        ctx_snapshot: dict[str, Any],
    ) -> None:
        """Persist (upsert) the current saga state."""

    @abc.abstractmethod
    async def load(self, saga_id: str) -> SagaRecord | None:
        """Return the latest record for *saga_id*, or ``None``."""


class InMemorySagaStore(SagaStore):
    """In-memory :class:`SagaStore` for tests and local development."""

    def __init__(self) -> None:
        self._records: dict[str, SagaRecord] = {}

    async def save(
        self,
        saga_id: str,
        state: SagaState,
        step_index: int,
        ctx_snapshot: dict[str, Any],
    ) -> None:
        self._records[saga_id] = SagaRecord(
            saga_id=saga_id,
            state=state,
            step_index=step_index,
            ctx_snapshot=dict(ctx_snapshot),
        )

    async def load(self, saga_id: str) -> SagaRecord | None:
        return self._records.get(saga_id)

    def all_records(self) -> dict[str, SagaRecord]:
        """Return all stored records (useful in tests)."""
        return dict(self._records)


__all__ = ["InMemorySagaStore", "SagaRecord", "SagaStore"]
