"""Unit tests for RedisCircuitBreaker (R-03).

Uses a FakeRedis implementation to avoid requiring a real Redis server.
Covers: state transitions, failure threshold, probe lock, reset, and
excluded exceptions.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock

import pytest

from mp_commons.resilience.circuit_breaker.errors import CircuitOpenError
from mp_commons.resilience.circuit_breaker.policy import CircuitBreakerPolicy
from mp_commons.resilience.circuit_breaker.redis_breaker import RedisCircuitBreaker
from mp_commons.resilience.circuit_breaker.state import CircuitBreakerState

# ---------------------------------------------------------------------------
# Minimal in-memory Redis stub
# ---------------------------------------------------------------------------


class FakeRedis:
    """Minimal async Redis stub that implements only the methods used by
    RedisCircuitBreaker, using a plain dict as storage."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> bytes | None:
        val = self._data.get(key)
        return val.encode() if val is not None else None

    async def set(
        self, key: str, value: str, *, nx: bool = False, xx: bool = False, px: int | None = None
    ) -> bool | None:
        if nx and key in self._data:
            return None  # NX = only set if Not eXists
        if xx and key not in self._data:
            return None  # XX = only set if eXists
        self._data[key] = str(value)
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._data:
                del self._data[k]
                count += 1
        return count

    async def execute_command(self, command: str, script: str, num_keys: int, *args: Any) -> bytes:
        """Simulate EVAL by running the Lua-equivalent logic in Python."""
        keys = list(args[:num_keys])
        argv = list(args[num_keys:])

        # _LUA_RECORD_FAILURE passes 2 ARGV (threshold + timestamp);
        # _LUA_RECORD_SUCCESS passes 1 ARGV (success_threshold only).
        if len(argv) == 2:
            # _LUA_RECORD_FAILURE
            current = int(self._data.get(keys[0], "0"))
            current += 1
            self._data[keys[0]] = str(current)
            threshold = int(argv[0])
            if current >= threshold:
                self._data[keys[1]] = "OPEN"
                self._data[keys[2]] = str(argv[1])
                return b"OPEN"
            return str(current).encode()
        else:
            # _LUA_RECORD_SUCCESS
            state = self._data.get(keys[1], "CLOSED")
            success_threshold = int(argv[0])
            if state == "HALF_OPEN":
                current = int(self._data.get(keys[0], "0"))
                current += 1
                self._data[keys[0]] = str(current)
                if current >= success_threshold:
                    self._data[keys[1]] = "CLOSED"
                    self._data[keys[0]] = "0"
                    if keys[2] in self._data:
                        del self._data[keys[2]]
                    return b"CLOSED"
                return b"HALF_OPEN"
            elif state == "CLOSED":
                self._data[keys[0]] = "0"
                return b"CLOSED"
            return state.encode()


def _make_breaker(
    policy: CircuitBreakerPolicy | None = None,
    redis: FakeRedis | None = None,
) -> tuple[RedisCircuitBreaker, FakeRedis]:
    r = redis or FakeRedis()
    b = RedisCircuitBreaker(
        name="test-svc",
        redis=r,
        policy=policy
        or CircuitBreakerPolicy(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=30.0,
        ),
    )
    return b, r


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    @pytest.mark.asyncio
    async def test_starts_closed(self):
        b, _ = _make_breaker()
        assert await b.state() == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_allows_calls_when_closed(self):
        b, _ = _make_breaker()
        result = await b.call(AsyncMock(return_value=42))
        assert result == 42


# ---------------------------------------------------------------------------
# CLOSED → OPEN transition
# ---------------------------------------------------------------------------


class TestClosedToOpen:
    @pytest.mark.asyncio
    async def test_opens_after_failure_threshold(self):
        b, _ = _make_breaker(CircuitBreakerPolicy(failure_threshold=3))

        async def fail():
            raise RuntimeError("err")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await b.call(fail)

        assert await b.state() == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_open_rejects_calls(self):
        b, _ = _make_breaker(CircuitBreakerPolicy(failure_threshold=2))

        async def fail():
            raise RuntimeError("err")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await b.call(fail)

        with pytest.raises(CircuitOpenError):
            await b.call(AsyncMock(return_value="should not run"))

    @pytest.mark.asyncio
    async def test_does_not_open_before_threshold(self):
        b, _ = _make_breaker(CircuitBreakerPolicy(failure_threshold=5))

        async def fail():
            raise RuntimeError("err")

        for _ in range(4):
            with pytest.raises(RuntimeError):
                await b.call(fail)

        assert await b.state() != CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_excluded_exceptions_do_not_count(self):
        policy = CircuitBreakerPolicy(
            failure_threshold=2,
            excluded_exceptions=(ValueError,),
        )
        b, _ = _make_breaker(policy)

        async def raise_value_error():
            raise ValueError("excluded")

        for _ in range(5):
            with pytest.raises(ValueError):
                await b.call(raise_value_error)

        # Should still be CLOSED because ValueError is excluded
        assert await b.state() == CircuitBreakerState.CLOSED


# ---------------------------------------------------------------------------
# OPEN → HALF_OPEN → CLOSED transition
# ---------------------------------------------------------------------------


class TestHalfOpenRecovery:
    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self):
        policy = CircuitBreakerPolicy(failure_threshold=2, timeout_seconds=0.0)
        b, r = _make_breaker(policy)

        async def fail():
            raise RuntimeError("err")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await b.call(fail)

        # opened_at was set; timeout_seconds=0 → immediately eligible
        # We need opened_at to be old enough — set it to the past
        r._data[b._key_opened_at] = str(time.time() - 1.0)
        state = await b._maybe_transition_half_open(CircuitBreakerState.OPEN)
        assert state == CircuitBreakerState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_probe_succeeds_then_closes(self):
        policy = CircuitBreakerPolicy(failure_threshold=2, timeout_seconds=0.0, success_threshold=1)
        b, r = _make_breaker(policy)

        # Manually set HALF_OPEN state
        r._data[b._key_state] = "HALF_OPEN"

        result = await b.call(AsyncMock(return_value="recovered"))
        assert result == "recovered"
        assert await b.state() == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_probe_locked_out(self):
        policy = CircuitBreakerPolicy(failure_threshold=2)
        b, r = _make_breaker(policy)

        r._data[b._key_state] = "HALF_OPEN"
        # Simulate another instance holds the probe lock
        r._data[b._key_probe_lock] = "1"

        with pytest.raises(CircuitOpenError):
            await b.call(AsyncMock(return_value="x"))


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class TestReset:
    @pytest.mark.asyncio
    async def test_reset_clears_state(self):
        b, _r = _make_breaker(CircuitBreakerPolicy(failure_threshold=2))

        async def fail():
            raise RuntimeError("err")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await b.call(fail)

        assert await b.state() == CircuitBreakerState.OPEN
        await b.reset()
        assert await b.state() == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_reset_idempotent(self):
        b, _ = _make_breaker()
        await b.reset()  # reset on a clean breaker must not raise
        assert await b.state() == CircuitBreakerState.CLOSED
