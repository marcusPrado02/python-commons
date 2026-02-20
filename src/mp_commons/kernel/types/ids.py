"""String-based identifier value objects."""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any

from mp_commons.kernel.errors.domain import ValidationError


def _uuid7_str() -> str:
    """Generate a UUID v7 string, falling back to UUID v4 when uuid_utils is absent."""
    try:
        import uuid_utils  # type: ignore[import-untyped]

        return str(uuid_utils.uuid7())
    except ImportError:
        return str(uuid.uuid4())


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
    """Generic entity identifier backed by a UUID (v7 when available, v4 fallback).

    Examples::

        eid = EntityId.generate()           # new random id
        eid = EntityId.from_str("abc-123")  # from existing string
        eid = EntityId("abc-123")           # direct construction
    """

    @classmethod
    def generate(cls) -> "EntityId":
        """Return a new random ``EntityId``."""
        return cls(_uuid7_str())

    @classmethod
    def from_str(cls, value: str) -> "EntityId":
        """Construct from an existing string identifier."""
        return cls(value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: Any,
    ) -> Any:
        try:
            from pydantic_core import core_schema

            return core_schema.no_info_plain_validator_function(
                lambda v: cls(v) if isinstance(v, str) else v,
                serialization=core_schema.to_string_ser_schema(),
            )
        except ImportError:
            raise


@dataclasses.dataclass(frozen=True, slots=True)
class TenantId(_StrId):
    """Identifies a tenant in a multi-tenant system."""


@dataclasses.dataclass(frozen=True, slots=True)
class CorrelationId(_StrId):
    """Request correlation / trace identifier."""

    @classmethod
    def generate(cls) -> "CorrelationId":
        """Return a new random ``CorrelationId``."""
        return cls(_uuid7_str())


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
