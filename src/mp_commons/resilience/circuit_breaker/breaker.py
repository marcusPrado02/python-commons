"""Resilience – CircuitBreaker implementation."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable, TypeVar

from mp_commons.kernel.errors import ExternalServiceError
from mp_commons.resilience.circuit_breaker.state import CircuitBreakerState
from mp_commons.resilience.circuit_breaker.policy import CircuitBreakerPolicy

T = TypeVar("T")
logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Thread-safe (asyncio-safe) circuit breaker implementation."""

    def __init__(self, name: str, policy: CircuitBreakerPolicy | None = None) -> None:
        self.name = name
        self._policy = policy or CircuitBreakerPolicy()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            self._maybe_transition_half_open()
            if self._state == CircuitBreakerState.OPEN:
                raise ExternalServiceError(self.name, f"Circuit breaker '{self.name}' is OPEN")

        try:
            result = await func()
            async with self._lock:
                self._on_success()
            return result
        except Exception as exc:
            if isinstance(exc, self._policy.excluded_exceptions):
                raise
            async with self._lock:
                self._on_failure()
            raise

    def _maybe_transition_half_open(self) -> None:
        if (
            self._state == CircuitBreakerState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self._policy.timeout_seconds
        ):
            logger.info("circuit_breaker.half_open name=%s", self.name)
            self._state = CircuitBreakerState.HALF_OPEN
            self._success_count = 0

    def _on_success(self) -> None:
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._policy.success_threshold:
                logger.info("circuit_breaker.closed name=%s", self.name)
                self._state = CircuitBreakerState.CLOSED
                self._failure_count = 0
        elif self._state == CircuitBreakerState.CLOSED:
            self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        logger.warning(
            "circuit_breaker.failure name=%s count=%d threshold=%d",
            self.name, self._failure_count, self._policy.failure_threshold,
        )
        if self._failure_count >= self._policy.failure_threshold:
            logger.error("circuit_breaker.opened name=%s", self.name)
            self._state = CircuitBreakerState.OPEN
            self._opened_at = time.monotonic()
            self._failure_count = 0


__all__ = ["CircuitBreaker"]
