"""Unit tests for TimeoutPolicy and Deadline — §18."""

from __future__ import annotations

import asyncio
import time

import pytest

from mp_commons.resilience.timeouts import Deadline, TimeoutPolicy
from mp_commons.kernel.errors import TimeoutError as AppTimeoutError


# ---------------------------------------------------------------------------
# Deadline (18.1 — deadline helper)
# ---------------------------------------------------------------------------


class TestDeadline:
    def test_not_expired_immediately_after_creation(self) -> None:
        d = Deadline.after(seconds=60.0)
        assert not d.is_expired

    def test_remaining_seconds_positive(self) -> None:
        d = Deadline.after(seconds=60.0)
        assert d.remaining_seconds > 0.0

    def test_remaining_seconds_caps_at_zero_when_expired(self) -> None:
        d = Deadline.after(seconds=-1.0)
        assert d.remaining_seconds == 0.0

    def test_is_expired_when_in_past(self) -> None:
        d = Deadline.after(seconds=-1.0)
        assert d.is_expired

    def test_raise_if_expired_raises_when_in_past(self) -> None:
        d = Deadline.after(seconds=-1.0)
        with pytest.raises(AppTimeoutError):
            d.raise_if_expired()

    def test_raise_if_expired_does_not_raise_when_fresh(self) -> None:
        d = Deadline.after(seconds=60.0)
        d.raise_if_expired()  # should not raise

    def test_frozen(self) -> None:
        d = Deadline.after(seconds=10.0)
        with pytest.raises((AttributeError, TypeError)):
            d.expires_at = d.expires_at  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TimeoutPolicy (18.1)
# ---------------------------------------------------------------------------


class TestTimeoutPolicy:
    def test_fast_call_returns_result(self) -> None:
        async def fast() -> str:
            return "done"

        async def run() -> str:
            policy = TimeoutPolicy(timeout_seconds=5.0)
            return await policy.execute(fast)

        result = asyncio.run(run())
        assert result == "done"

    def test_slow_call_raises_app_timeout_error(self) -> None:
        async def slow() -> None:
            await asyncio.sleep(10.0)

        async def run() -> None:
            policy = TimeoutPolicy(timeout_seconds=0.01)
            await policy.execute(slow)

        with pytest.raises(AppTimeoutError):
            asyncio.run(run())

    def test_timeout_message_contains_seconds(self) -> None:
        async def slow() -> None:
            await asyncio.sleep(10.0)

        async def run() -> None:
            policy = TimeoutPolicy(timeout_seconds=0.01)
            await policy.execute(slow)

        with pytest.raises(AppTimeoutError, match="0.01"):
            asyncio.run(run())

    def test_exception_in_fast_fn_propagates(self) -> None:
        async def failing() -> None:
            raise ValueError("inner error")

        async def run() -> None:
            policy = TimeoutPolicy(timeout_seconds=5.0)
            await policy.execute(failing)

        with pytest.raises(ValueError, match="inner error"):
            asyncio.run(run())

    def test_timeout_policy_is_dataclass(self) -> None:
        p = TimeoutPolicy(timeout_seconds=1.0)
        assert p.timeout_seconds == 1.0


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.resilience.timeouts")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing"
