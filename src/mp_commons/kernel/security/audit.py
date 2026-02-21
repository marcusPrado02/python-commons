"""Kernel security – AuditEvent, AuditStore, InMemoryAuditStore."""

from __future__ import annotations

import abc
import dataclasses
from datetime import UTC, datetime
from typing import Literal

from mp_commons.kernel.types.ids import EntityId


# ---------------------------------------------------------------------------
# AuditEvent
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AuditEvent:
    """An immutable record of a security-relevant action.

    Parameters
    ----------
    event_id:
        Unique identifier for this audit record.  Defaults to a freshly
        generated :class:`~mp_commons.kernel.types.ids.EntityId`.
    principal_id:
        Subject that performed the action (e.g. user id, service account).
    action:
        Human-readable action label, e.g. ``"orders:create"`` or
        ``"admin:delete_user"``.
    resource_type:
        Category of the resource affected (e.g. ``"Order"``, ``"User"``).
    resource_id:
        Identifier of the specific resource instance.
    outcome:
        Either ``"allow"`` or ``"deny"``.
    occurred_at:
        UTC timestamp of the action.  Defaults to *now*.
    metadata:
        Arbitrary extra context (IP address, correlation id, …).
    """

    principal_id: str
    action: str
    resource_type: str
    resource_id: str
    outcome: Literal["allow", "deny"]
    event_id: EntityId = dataclasses.field(
        default_factory=EntityId.generate
    )
    occurred_at: datetime = dataclasses.field(
        default_factory=lambda: datetime.now(UTC)
    )
    metadata: dict = dataclasses.field(default_factory=dict)  # type: ignore[type-arg]

    def is_denied(self) -> bool:
        return self.outcome == "deny"

    def is_allowed(self) -> bool:
        return self.outcome == "allow"


# ---------------------------------------------------------------------------
# AuditStore Protocol
# ---------------------------------------------------------------------------


class AuditStore(abc.ABC):
    """Port — persistent audit log storage.

    Implementations live in ``adapters/``: e.g.
    :class:`~mp_commons.adapters.sqlalchemy.audit.SQLAlchemyAuditStore`.
    Use :class:`InMemoryAuditStore` in unit tests.
    """

    @abc.abstractmethod
    async def record(self, event: AuditEvent) -> None:
        """Persist *event* to the audit log."""

    @abc.abstractmethod
    async def query(
        self,
        *,
        principal_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        action_filter: str | None = None,
        outcome: Literal["allow", "deny"] | None = None,
        limit: int = 1000,
    ) -> list[AuditEvent]:
        """Return audit events matching all supplied filters.

        All parameters are optional; omitting a parameter applies no filter
        for that dimension.  Results are ordered oldest-first.
        """


# ---------------------------------------------------------------------------
# InMemoryAuditStore
# ---------------------------------------------------------------------------


class InMemoryAuditStore(AuditStore):
    """List-backed audit store for unit tests and local development."""

    def __init__(self) -> None:
        self._records: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> None:
        self._records.append(event)

    async def query(
        self,
        *,
        principal_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        action_filter: str | None = None,
        outcome: Literal["allow", "deny"] | None = None,
        limit: int = 1000,
    ) -> list[AuditEvent]:
        results = self._records
        if principal_id is not None:
            results = [e for e in results if e.principal_id == principal_id]
        if from_dt is not None:
            results = [e for e in results if e.occurred_at >= from_dt]
        if to_dt is not None:
            results = [e for e in results if e.occurred_at <= to_dt]
        if action_filter is not None:
            results = [e for e in results if action_filter in e.action]
        if outcome is not None:
            results = [e for e in results if e.outcome == outcome]
        # oldest-first
        results = sorted(results, key=lambda e: e.occurred_at)
        return results[:limit]

    def all(self) -> list[AuditEvent]:
        """Return all stored events (helper for test assertions)."""
        return list(self._records)


__all__ = ["AuditEvent", "AuditStore", "InMemoryAuditStore"]
