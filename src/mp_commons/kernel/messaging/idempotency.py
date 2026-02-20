"""Kernel messaging – idempotency ports."""
from __future__ import annotations

import abc
import dataclasses
from datetime import UTC, datetime
from enum import Enum


class DeduplicationPolicy(str, Enum):
    """How to handle duplicate requests."""

    RETURN_CACHED = "RETURN_CACHED"
    RAISE_ERROR = "RAISE_ERROR"
    IGNORE = "IGNORE"


@dataclasses.dataclass(frozen=True)
class IdempotencyKey:
    """Composite idempotency key = (client_key, operation)."""

    client_key: str
    operation: str

    def __str__(self) -> str:
        return f"{self.operation}:{self.client_key}"


@dataclasses.dataclass
class IdempotencyRecord:
    """Stored result of an idempotent operation."""

    key: str
    response: bytes | None = None
    status: str = "PROCESSING"
    created_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None


class IdempotencyStore(abc.ABC):
    """Port: store / retrieve idempotency records."""

    @abc.abstractmethod
    async def get(self, key: IdempotencyKey) -> IdempotencyRecord | None: ...

    @abc.abstractmethod
    async def save(self, key: IdempotencyKey, record: IdempotencyRecord) -> None: ...

    @abc.abstractmethod
    async def complete(self, key: IdempotencyKey, response: bytes) -> None: ...


__all__ = [
    "DeduplicationPolicy",
    "IdempotencyKey",
    "IdempotencyRecord",
    "IdempotencyStore",
]
