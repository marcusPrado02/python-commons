"""String-based identifier value objects."""

from __future__ import annotations

import dataclasses

from mp_commons.kernel.errors.domain import ValidationError


@dataclasses.dataclass(frozen=True, slots=True)
class _StrId:
    """Base for string-typed identifiers."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError(f"{type(self).__name__} must not be empty")

    def __str__(self) -> str:
        return self.value


@dataclasses.dataclass(frozen=True, slots=True)
class EntityId(_StrId):
    """Generic entity identifier (opaque string)."""


@dataclasses.dataclass(frozen=True, slots=True)
class TenantId(_StrId):
    """Identifies a tenant in a multi-tenant system."""


@dataclasses.dataclass(frozen=True, slots=True)
class CorrelationId(_StrId):
    """Request correlation / trace identifier."""


@dataclasses.dataclass(frozen=True, slots=True)
class TraceId(_StrId):
    """Distributed tracing trace identifier."""


@dataclasses.dataclass(frozen=True, slots=True)
class UserId(_StrId):
    """Authenticated user identifier."""


__all__ = [
    "CorrelationId",
    "EntityId",
    "TenantId",
    "TraceId",
    "UserId",
]
