"""Application rate limiting – RateLimiter, RateLimitDecision, RateLimitResult, Quota."""
from __future__ import annotations

import abc
import dataclasses
from datetime import UTC, datetime
from enum import Enum


class RateLimitDecision(str, Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


@dataclasses.dataclass(frozen=True)
class Quota:
    """Rate limit quota rule."""
    key: str
    limit: int
    window_seconds: int

    @property
    def window_label(self) -> str:
        return f"{self.limit} req/{self.window_seconds}s"


@dataclasses.dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    decision: RateLimitDecision
    remaining: int
    reset_at: datetime
    quota: Quota

    @property
    def allowed(self) -> bool:
        return self.decision == RateLimitDecision.ALLOWED

    @property
    def retry_after_seconds(self) -> float:
        delta = self.reset_at - datetime.now(UTC)
        return max(0.0, delta.total_seconds())


class RateLimiter(abc.ABC):
    """Port: check whether a keyed request is within quota."""

    @abc.abstractmethod
    async def check(self, quota: Quota, identifier: str) -> RateLimitResult: ...

    @abc.abstractmethod
    async def reset(self, quota: Quota, identifier: str) -> None: ...


__all__ = ["Quota", "RateLimitDecision", "RateLimitResult", "RateLimiter"]
