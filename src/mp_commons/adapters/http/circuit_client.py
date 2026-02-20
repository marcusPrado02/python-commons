"""HTTP adapter – CircuitBreakingHttpClient."""
from __future__ import annotations

from typing import Any

from mp_commons.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerPolicy
from mp_commons.adapters.http.client import HttpxHttpClient


class CircuitBreakingHttpClient(HttpxHttpClient):
    """HTTP client with circuit breaker protection."""

    def __init__(
        self,
        base_url: str = "",
        timeout: float = 10.0,
        cb_name: str = "http-client",
        cb_policy: CircuitBreakerPolicy | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(base_url, timeout, **kwargs)
        self._cb = CircuitBreaker(cb_name, cb_policy)

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        return await self._cb.call(
            lambda: super(CircuitBreakingHttpClient, self)._request(method, url, **kwargs)
        )


__all__ = ["CircuitBreakingHttpClient"]
