"""Redis-backed distributed circuit breaker (R-03).

Shares circuit breaker state across all service instances by persisting it in
Redis.  Uses atomic Lua scripts for CLOSED→OPEN transitions and a short-lived
Redis lock to ensure only one instance probes the backend in HALF_OPEN state.

Key layout (all keys are namespaced under *prefix*):

* ``{prefix}:state``      — string: ``"CLOSED"`` | ``"OPEN"`` | ``"HALF_OPEN"``
* ``{prefix}:failures``   — integer failure counter (reset on success / reset)
* ``{prefix}:opened_at``  — float UNIX timestamp when the breaker was opened
* ``{prefix}:probe_lock`` — ephemeral lock (SET NX PX) for HALF_OPEN probe

Usage::

    from mp_commons.resilience.circuit_breaker.redis_breaker import RedisCircuitBreaker
    from mp_commons.resilience.circuit_breaker.policy import CircuitBreakerPolicy

    redis = await aioredis.from_url("redis://localhost")
    breaker = RedisCircuitBreaker(
        name="payment-service",
        redis=redis,
        policy=CircuitBreakerPolicy(failure_threshold=5, timeout_seconds=30.0),
    )

    try:
        result = await breaker.call(my_async_fn)
    except CircuitOpenError:
        # fast-fail while circuit is open
        ...
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
import time
from typing import Any, TypeVar

from mp_commons.resilience.circuit_breaker.errors import CircuitOpenError
from mp_commons.resilience.circuit_breaker.policy import CircuitBreakerPolicy
from mp_commons.resilience.circuit_breaker.state import CircuitBreakerState

T = TypeVar("T")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lua scripts — executed atomically on the Redis server via EVAL command.
# These are Redis Lua scripts (not Python eval) and are pre-written strings,
# not user-supplied code.
# ---------------------------------------------------------------------------

# Increment failure counter; if it reaches *threshold*, transition to OPEN.
# KEYS[1] = failures key, KEYS[2] = state key, KEYS[3] = opened_at key
# ARGV[1] = failure_threshold, ARGV[2] = current unix timestamp
_LUA_RECORD_FAILURE = """
local failures = redis.call('INCR', KEYS[1])
if failures >= tonumber(ARGV[1]) then
    redis.call('SET', KEYS[2], 'OPEN')
    redis.call('SET', KEYS[3], ARGV[2])
    return 'OPEN'
else
    return tostring(failures)
end
"""

# On success: if state is HALF_OPEN, count towards closing.
# KEYS[1] = failures/successes key, KEYS[2] = state key, KEYS[3] = opened_at
# ARGV[1] = success_threshold
_LUA_RECORD_SUCCESS = """
local state = redis.call('GET', KEYS[2]) or 'CLOSED'
if state == 'HALF_OPEN' then
    local succ = redis.call('INCR', KEYS[1])
    if succ >= tonumber(ARGV[1]) then
        redis.call('SET',  KEYS[2], 'CLOSED')
        redis.call('SET',  KEYS[1], '0')
        redis.call('DEL',  KEYS[3])
        return 'CLOSED'
    end
    return 'HALF_OPEN'
elseif state == 'CLOSED' then
    redis.call('SET', KEYS[1], '0')
    return 'CLOSED'
end
return state
"""


class RedisCircuitBreaker:
    """Distributed circuit breaker backed by Redis.

    All service instances sharing the same *prefix* / *name* share a single
    circuit breaker state.  The ``CLOSED → OPEN`` transition is serialised via
    an atomic Lua script, so the threshold is never breached by race conditions.

    Parameters
    ----------
    name:
        Logical name for this breaker (used in log messages and as the Redis
        key prefix together with *key_prefix*).
    redis:
        An async Redis client (``redis.asyncio.Redis`` or compatible).
    policy:
        :class:`~mp_commons.resilience.circuit_breaker.policy.CircuitBreakerPolicy`
        controlling thresholds and timeouts.
    key_prefix:
        Namespace prefix for all Redis keys.  Default: ``"circuit_breaker"``.
    half_open_probe_ttl_ms:
        TTL in milliseconds of the HALF_OPEN probe lock.  Only one instance
        acquires the lock and probes the backend.  Default: ``5000`` ms.
    """

    def __init__(
        self,
        name: str,
        redis: Any,
        policy: CircuitBreakerPolicy | None = None,
        key_prefix: str = "circuit_breaker",
        half_open_probe_ttl_ms: int = 5000,
    ) -> None:
        self.name = name
        self._redis = redis
        self._policy = policy or CircuitBreakerPolicy()
        self._half_open_probe_ttl_ms = half_open_probe_ttl_ms

        prefix = f"{key_prefix}:{name}"
        self._key_state = f"{prefix}:state"
        self._key_failures = f"{prefix}:failures"
        self._key_opened_at = f"{prefix}:opened_at"
        self._key_probe_lock = f"{prefix}:probe_lock"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def state(self) -> CircuitBreakerState:
        """Read the current state from Redis (network call)."""
        raw = await self._redis.get(self._key_state)
        if raw is None:
            return CircuitBreakerState.CLOSED
        return CircuitBreakerState(raw.decode() if isinstance(raw, bytes) else raw)

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        """Execute *func* guarded by the circuit breaker.

        Raises
        ------
        CircuitOpenError
            If the breaker is OPEN and the timeout has not yet elapsed, or if
            the breaker is HALF_OPEN and another instance holds the probe lock.
        """
        current_state = await self.state()
        current_state = await self._maybe_transition_half_open(current_state)

        if current_state == CircuitBreakerState.OPEN:
            raise CircuitOpenError(self.name)

        if current_state == CircuitBreakerState.HALF_OPEN:
            # Only one instance may probe at a time — acquire a short-lived lock
            acquired = await self._redis.set(
                self._key_probe_lock,
                "1",
                nx=True,
                px=self._half_open_probe_ttl_ms,
            )
            if not acquired:
                raise CircuitOpenError(self.name)

        try:
            result = await func()
            await self._on_success()
            return result
        except Exception as exc:
            if isinstance(exc, self._policy.excluded_exceptions):
                raise
            await self._on_failure()
            raise

    async def reset(self) -> None:
        """Manually reset the breaker to CLOSED and clear all counters."""
        await self._redis.delete(
            self._key_state,
            self._key_failures,
            self._key_opened_at,
            self._key_probe_lock,
        )
        logger.info("redis_circuit_breaker.reset name=%s", self.name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _maybe_transition_half_open(
        self, current_state: CircuitBreakerState
    ) -> CircuitBreakerState:
        if current_state != CircuitBreakerState.OPEN:
            return current_state

        raw = await self._redis.get(self._key_opened_at)
        if raw is None:
            return current_state

        opened_at = float(raw.decode() if isinstance(raw, bytes) else raw)
        if time.time() - opened_at >= self._policy.timeout_seconds:
            # Transition to HALF_OPEN — XX ensures we only update if key exists
            await self._redis.set(
                self._key_state,
                CircuitBreakerState.HALF_OPEN.value,
                xx=True,
            )
            logger.info("redis_circuit_breaker.half_open name=%s", self.name)
            return CircuitBreakerState.HALF_OPEN
        return current_state

    async def _on_failure(self) -> None:
        # redis.execute_command sends the Redis EVAL command with Lua script
        result = await self._redis.execute_command(
            "EVAL",
            _LUA_RECORD_FAILURE,
            3,
            self._key_failures,
            self._key_state,
            self._key_opened_at,
            self._policy.failure_threshold,
            str(time.time()),
        )
        if result in (b"OPEN", "OPEN"):
            logger.error("redis_circuit_breaker.opened name=%s", self.name)

    async def _on_success(self) -> None:
        result = await self._redis.execute_command(
            "EVAL",
            _LUA_RECORD_SUCCESS,
            3,
            self._key_failures,
            self._key_state,
            self._key_opened_at,
            self._policy.success_threshold,
        )
        state_val = result.decode() if isinstance(result, bytes) else str(result)
        if state_val == "CLOSED":
            logger.info("redis_circuit_breaker.closed name=%s", self.name)
        # Release probe lock regardless of outcome
        await self._redis.delete(self._key_probe_lock)


__all__ = ["RedisCircuitBreaker"]
