"""Resilience – Deadline."""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

from mp_commons.kernel.errors import TimeoutError as AppTimeoutError


@dataclasses.dataclass(frozen=True)
class Deadline:
    """An absolute deadline derived from a timeout."""
    expires_at: datetime

    @classmethod
    def after(cls, seconds: float) -> "Deadline":
        return cls(expires_at=datetime.now(UTC) + timedelta(seconds=seconds))

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, (self.expires_at - datetime.now(UTC)).total_seconds())

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at

    def raise_if_expired(self) -> None:
        if self.is_expired:
            raise AppTimeoutError("Deadline exceeded")


__all__ = ["Deadline"]
