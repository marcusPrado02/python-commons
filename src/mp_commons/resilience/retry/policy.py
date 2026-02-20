"""Resilience – RetryPolicy and RetryExecutor."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, TypeVar

from mp_commons.resilience.retry.backoff import BackoffStrategy, ExponentialBackoff
from mp_commons.resilience.retry.jitter import FullJitter, JitterStrategy

T = TypeVar("T")
logger = logging.getLogger(__name__)


class RetryPolicy:
    """Configurable retry policy."""

    def __init__(
        self,
        max_attempts: int = 3,
        backoff: BackoffStrategy | None = None,
        jitter: JitterStrategy | None = None,
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    ) -> None:
        self.max_attempts = max_attempts
        self.backoff = backoff or ExponentialBackoff()
        self.jitter = jitter or FullJitter()
        self.retryable_exceptions = retryable_exceptions

    def _should_retry(self, exc: Exception) -> bool:
        return isinstance(exc, self.retryable_exceptions)

    def execute(self, func: Callable[[], T]) -> T:
        """Execute *func* synchronously with retry."""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return func()
            except Exception as exc:
                if not self._should_retry(exc) or attempt == self.max_attempts:
                    raise
                last_exc = exc
                delay = self.jitter.apply(self.backoff.compute(attempt))
                logger.debug("retry attempt=%d delay=%.2fs exc=%r", attempt, delay, exc)
                time.sleep(delay)
        raise last_exc  # type: ignore[misc]

    async def execute_async(self, func: Callable[[], Awaitable[T]]) -> T:
        """Execute *func* asynchronously with retry."""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await func()
            except Exception as exc:
                if not self._should_retry(exc) or attempt == self.max_attempts:
                    raise
                last_exc = exc
                delay = self.jitter.apply(self.backoff.compute(attempt))
                logger.debug("retry attempt=%d delay=%.2fs exc=%r", attempt, delay, exc)
                await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]


class RetryExecutor:
    """Decorator-friendly wrapper around ``RetryPolicy``."""

    def __init__(self, policy: RetryPolicy) -> None:
        self._policy = policy

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        import functools

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await self._policy.execute_async(lambda: func(*args, **kwargs))

        return wrapper


__all__ = ["RetryExecutor", "RetryPolicy"]
