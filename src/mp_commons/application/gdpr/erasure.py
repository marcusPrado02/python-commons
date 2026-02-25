"""Application GDPR – DataSubjectRequest, ErasureService, DataPortabilityExporter."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Protocol, runtime_checkable

__all__ = [
    "ConsentRecord",
    "ConsentStore",
    "DataErasedEvent",
    "DataSubjectRequest",
    "DataPortabilityExporter",
    "Erasable",
    "ErasureResult",
    "ErasureService",
    "InMemoryConsentStore",
]


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DataSubjectRequest:
    subject_id: str
    type: Literal["erasure", "portability", "rectification"]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


@dataclass(frozen=True)
class ErasureResult:
    scope: str
    success: bool
    detail: str | None = None


@dataclass(frozen=True)
class DataErasedEvent:
    subject_id: str
    results: tuple[ErasureResult, ...]
    erased_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------

@runtime_checkable
class Erasable(Protocol):
    @property
    def scope(self) -> str: ...
    async def erase(self, subject_id: str) -> ErasureResult: ...


@runtime_checkable
class Exportable(Protocol):
    @property
    def scope(self) -> str: ...
    async def export(self, subject_id: str) -> dict: ...


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

class ErasureService:
    """Orchestrates erasure across all registered Erasable handlers."""

    def __init__(self) -> None:
        self._handlers: list[Erasable] = []
        self.events: list[DataErasedEvent] = []

    def register(self, handler: Erasable) -> None:
        self._handlers.append(handler)

    async def erase(self, subject_id: str) -> DataErasedEvent:
        results: list[ErasureResult] = []
        for handler in self._handlers:
            try:
                result = await handler.erase(subject_id)
            except Exception as exc:  # noqa: BLE001
                result = ErasureResult(scope=handler.scope, success=False, detail=str(exc))
            results.append(result)
        event = DataErasedEvent(subject_id=subject_id, results=tuple(results))
        self.events.append(event)
        return event


class DataPortabilityExporter:
    """Aggregates data from all registered Exportable handlers."""

    def __init__(self) -> None:
        self._handlers: list[Exportable] = []

    def register(self, handler: Exportable) -> None:
        self._handlers.append(handler)

    async def export(self, subject_id: str) -> dict:
        merged: dict = {}
        for handler in self._handlers:
            try:
                data = await handler.export(subject_id)
                merged[handler.scope] = data
            except Exception as exc:  # noqa: BLE001
                merged[handler.scope] = {"error": str(exc)}
        return merged


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------

@dataclass
class ConsentRecord:
    subject_id: str
    purpose: str
    granted: bool
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    withdrawn_at: datetime | None = None

    def withdraw(self) -> None:
        self.granted = False
        self.withdrawn_at = datetime.now(timezone.utc)


@runtime_checkable
class ConsentStore(Protocol):
    async def save(self, record: ConsentRecord) -> None: ...
    async def find(self, subject_id: str, purpose: str) -> ConsentRecord | None: ...
    async def list_for_subject(self, subject_id: str) -> list[ConsentRecord]: ...


class InMemoryConsentStore:
    def __init__(self) -> None:
        self._records: dict[str, ConsentRecord] = {}

    def _key(self, subject_id: str, purpose: str) -> str:
        return f"{subject_id}:{purpose}"

    async def save(self, record: ConsentRecord) -> None:
        self._records[self._key(record.subject_id, record.purpose)] = record

    async def find(self, subject_id: str, purpose: str) -> ConsentRecord | None:
        return self._records.get(self._key(subject_id, purpose))

    async def list_for_subject(self, subject_id: str) -> list[ConsentRecord]:
        return [r for r in self._records.values() if r.subject_id == subject_id]
