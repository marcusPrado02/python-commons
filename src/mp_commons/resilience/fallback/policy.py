from __future__ import annotations

from typing import Any, Awaitable, Callable, Generic, TypeVar

__all__ = [
    "CachedFallbackPolicy",
    "FallbackPolicy",
]

T = TypeVar("T")
_MISSING: Any = object()


class FallbackPolicy(Generic[T]):
    """Executes *fn*; on listed exceptions invokes *fallback* instead."""

    def __init__(
        self,
        fallback: Callable[[], Awaitable[T]] | T,
        on_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        self._fallback = fallback
        self._on_exceptions = on_exceptions

    async def execute(self, fn: Callable[[], Awaitable[T]]) -> T:
        try:
            return await fn()
        except BaseException as exc:
            if isinstance(exc, self._on_exceptions):
                if callable(self._fallback):
                    return await self._fallback()  # type: ignore[return-value]
                return self._fallback  # type: ignore[return-value]
            raise


class CachedFallbackPolicy(FallbackPolicy[T]):
    """Extends FallbackPolicy by caching the last successful result."""

    def __init__(
        self,
        fallback: Callable[[], Awaitable[T]] | T,
        on_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        super().__init__(fallback, on_exceptions)
        self._last_success: Any = _MISSING

    @property
    def has_cached(self) -> bool:
        return self._last_success is not _MISSING

    @property
    def cached_value(self) -> T:
        if self._last_success is _MISSING:
            raise ValueError("No cached value available")
        return self._last_success

    async def execute(self, fn: Callable[[], Awaitable[T]]) -> T:
        try:
            result = await fn()
            self._last_success = result
            return result
        except BaseException as exc:
            if isinstance(exc, self._on_exceptions):
                if self._last_success is not _MISSING:
                    return self._last_success
                if callable(self._fallback):
                    return await self._fallback()  # type: ignore[return-value]
                return self._fallback  # type: ignore[return-value]
            raise
