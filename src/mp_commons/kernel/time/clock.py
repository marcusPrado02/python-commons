"""Kernel time – Clock protocol + implementations."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """Port: abstract clock for deterministic testing."""

    def now(self) -> datetime: ...
    def today(self) -> date: ...
    def timestamp(self) -> float: ...


class SystemClock:
    """Production clock that delegates to ``datetime.now(UTC)``."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return datetime.now(UTC).date()

    def timestamp(self) -> float:
        return datetime.now(UTC).timestamp()


class FrozenClock:
    """Test clock pinned to a fixed point in time."""

    def __init__(self, fixed: datetime) -> None:
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed

    def today(self) -> date:
        return self._fixed.date()

    def timestamp(self) -> float:
        return self._fixed.timestamp()

    def advance(self, **kwargs: int | float) -> None:
        """Advance the frozen time by the given ``timedelta`` kwargs."""
        self._fixed += timedelta(**kwargs)


def utc_now() -> datetime:
    """Shorthand for ``datetime.now(UTC)``."""
    return datetime.now(UTC)


UtcNow = utc_now

__all__ = ["Clock", "FrozenClock", "SystemClock", "UtcNow", "utc_now"]
