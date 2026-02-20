"""HTTP adapter – RetryingHttpClient."""
from __future__ import annotations

from typing import Any

from mp_commons.kernel.errors import ExternalServiceError, TimeoutError as AppTimeoutError
from mp_commons.resilience.retry import ExponentialBackoff, FullJitter, RetryPolicy
from mp_commons.adapters.http.client import HttpxHttpClient


class RetryingHttpClient(HttpxHttpClient):
    """HTTP client with automatic retry on transient failures."""

    def __init__(self, base_url: str = "", timeout: float = 10.0, max_attempts: int = 3, **kwargs: Any) -> None:
        super().__init__(base_url, timeout, **kwargs)
        self._retry = RetryPolicy(
            max_attempts=max_attempts,
            backoff=ExponentialBackoff(base_delay=0.1),
            jitter=FullJitter(),
            retryable_exceptions=(ExternalServiceError, AppTimeoutError),
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        return await self._retry.execute_async(
            lambda: super(RetryingHttpClient, self)._request(method, url, **kwargs)
        )


__all__ = ["RetryingHttpClient"]
