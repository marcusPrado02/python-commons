"""Testing fakes – FakeClock factory."""
from __future__ import annotations

from datetime import UTC, datetime

from mp_commons.kernel.time import FrozenClock


def FakeClock() -> FrozenClock:
    """Return a ``FrozenClock`` pinned to 2026-01-01 12:00 UTC."""
    return FrozenClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))


__all__ = ["FakeClock"]
