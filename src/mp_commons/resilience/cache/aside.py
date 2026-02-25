from __future__ import annotations

import asyncio
import functools
from typing import Any, Awaitable, Callable, Generic, Protocol, TypeVar

__all__ = [
    "CacheAsidePolicy",
    "SimpleCache",
    "cache_aside",
]

T = TypeVar("T")


class SimpleCache(Protocol):
    async def get(self, key: str) -> Any: ...
    async def set(self, key: str, value: Any, ttl: float) -> None: ...


class CacheAsidePolicy(Generic[T]):
    """Implements the cache-aside (lazy-loading) pattern with stampede protection."""

    def __init__(
        self,
        cache: SimpleCache,
        ttl: float = 300.0,
        key_fn: Callable[..., str] | None = None,
    ) -> None:
        self._cache = cache
        self._ttl = ttl
        self._key_fn = key_fn
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_or_load(self, key: str, loader: Callable[[], Awaitable[T]]) -> T:
        cached = await self._cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        # Stampede protection: only one coroutine loads per key
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        async with self._locks[key]:
            # Double-check after acquiring lock
            cached = await self._cache.get(key)
            if cached is not None:
                return cached  # type: ignore[return-value]
            value = await loader()
            await self._cache.set(key, value, self._ttl)
            return value


def cache_aside(
    ttl: float = 300.0,
    key_fn: Callable[..., str] | None = None,
    cache: SimpleCache | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator version of CacheAsidePolicy."""
    from mp_commons.application.cache.tags import InMemoryTaggedCacheStore  # lazy import

    class _AdapterCache:
        def __init__(self, store: Any) -> None:
            self._store = store

        async def get(self, key: str) -> Any:
            return await self._store.get(key)

        async def set(self, key_: str, value: Any, ttl_: float) -> None:
            await self._store.set(key_, value, ttl=ttl_, tags=[])

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        _store = _AdapterCache(cache if cache is not None else InMemoryTaggedCacheStore())
        policy = CacheAsidePolicy(_store, ttl=ttl, key_fn=key_fn)

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            if key_fn is not None:
                key = key_fn(*args, **kwargs)
            else:
                key = f"{fn.__qualname__}:{args}:{sorted(kwargs.items())}"
            return await policy.get_or_load(key, lambda: fn(*args, **kwargs))

        wrapper._policy = policy  # type: ignore[attr-defined]
        return wrapper

    return decorator
