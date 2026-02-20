"""Testing chaos – FailureInjector."""
from __future__ import annotations

import random
from typing import Any


class FailureInjector:
    """Randomly raise an exception to simulate chaos scenarios."""

    def __init__(self, failure_rate: float = 0.2, exception_factory: Any = None) -> None:
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError("failure_rate must be between 0.0 and 1.0")
        self._rate = failure_rate
        self._factory = exception_factory or self._default_exception

    @staticmethod
    def _default_exception() -> Exception:
        from mp_commons.kernel.errors import ExternalServiceError
        return ExternalServiceError(service="chaos", message="Injected failure")

    async def call(self, coro: object) -> object:
        import inspect
        if random.random() < self._rate:  # noqa: S311
            raise self._factory()
        if inspect.isawaitable(coro):
            return await coro  # type: ignore[misc]
        return coro


__all__ = ["FailureInjector"]
