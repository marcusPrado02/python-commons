"""Unit tests for kernel time utilities."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from mp_commons.kernel.time import (
    Clock,
    FrozenClock,
    SystemClock,
    utc_now,
)


# ---------------------------------------------------------------------------
# SystemClock (7.1)
# ---------------------------------------------------------------------------


class TestSystemClock:
    def test_now_returns_utc_aware_datetime(self) -> None:
        clk = SystemClock()
        result = clk.now()
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert result.tzinfo == UTC or result.utcoffset().total_seconds() == 0  # type: ignore[union-attr]

    def test_today_returns_date(self) -> None:
        clk = SystemClock()
        result = clk.today()
        assert isinstance(result, date)
        assert not isinstance(result, datetime)

    def test_timestamp_returns_float(self) -> None:
        clk = SystemClock()
        ts = clk.timestamp()
        assert isinstance(ts, float)
        assert ts > 0

    def test_timestamp_close_to_now(self) -> None:
        clk = SystemClock()
        # within 1 second of wall clock
        expected = datetime.now(UTC).timestamp()
        assert abs(clk.timestamp() - expected) < 1.0

    def test_today_matches_now(self) -> None:
        clk = SystemClock()
        assert clk.today() == clk.now().date()


# ---------------------------------------------------------------------------
# FrozenClock (7.2)
# ---------------------------------------------------------------------------


class TestFrozenClock:
    def _fixed(self) -> datetime:
        return datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)

    def test_now_returns_fixed_time(self) -> None:
        clk = FrozenClock(self._fixed())
        assert clk.now() == self._fixed()

    def test_today_returns_correct_date(self) -> None:
        clk = FrozenClock(self._fixed())
        assert clk.today() == date(2024, 6, 15)

    def test_timestamp_matches_fixed(self) -> None:
        fixed = self._fixed()
        clk = FrozenClock(fixed)
        assert clk.timestamp() == fixed.timestamp()

    def test_advance_by_seconds(self) -> None:
        clk = FrozenClock(self._fixed())
        clk.advance(seconds=30)
        expected = datetime(2024, 6, 15, 12, 0, 30, tzinfo=UTC)
        assert clk.now() == expected

    def test_advance_by_minutes(self) -> None:
        clk = FrozenClock(self._fixed())
        clk.advance(minutes=5)
        expected = datetime(2024, 6, 15, 12, 5, 0, tzinfo=UTC)
        assert clk.now() == expected

    def test_advance_by_days(self) -> None:
        clk = FrozenClock(self._fixed())
        clk.advance(days=1)
        expected = datetime(2024, 6, 16, 12, 0, 0, tzinfo=UTC)
        assert clk.now() == expected

    def test_advance_combined(self) -> None:
        clk = FrozenClock(self._fixed())
        clk.advance(days=1, hours=2, minutes=3)
        expected = datetime(2024, 6, 16, 14, 3, 0, tzinfo=UTC)
        assert clk.now() == expected

    def test_advance_updates_today(self) -> None:
        clk = FrozenClock(self._fixed())
        clk.advance(days=2)
        assert clk.today() == date(2024, 6, 17)

    def test_advance_updates_timestamp(self) -> None:
        clk = FrozenClock(self._fixed())
        before = clk.timestamp()
        clk.advance(seconds=10)
        assert clk.timestamp() == pytest.approx(before + 10)

    def test_frozen_clock_is_clock(self) -> None:
        clk: Clock = FrozenClock(self._fixed())  # type: ignore[type-abstract]
        assert clk.now() == self._fixed()

    def test_today_is_date_not_datetime(self) -> None:
        clk = FrozenClock(self._fixed())
        result = clk.today()
        assert type(result) is date

    def test_multiple_advances_are_cumulative(self) -> None:
        clk = FrozenClock(self._fixed())
        clk.advance(seconds=10)
        clk.advance(seconds=20)
        expected = datetime(2024, 6, 15, 12, 0, 30, tzinfo=UTC)
        assert clk.now() == expected


# ---------------------------------------------------------------------------
# utc_now helper (7.3)
# ---------------------------------------------------------------------------


class TestUtcNow:
    def test_returns_utc_aware_datetime(self) -> None:
        result = utc_now()
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_close_to_system_time(self) -> None:
        now = datetime.now(UTC)
        result = utc_now()
        assert abs((result - now).total_seconds()) < 1.0


# ---------------------------------------------------------------------------
# Public surface smoke test (7.4)
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.kernel.time")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing from mp_commons.kernel.time"
