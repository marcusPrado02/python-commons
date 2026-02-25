"""Application cache – @cached decorator and CacheWarmupService."""
from __future__ import annotations

import functools
from typing import Any, Callable, Awaitable

from mp_commons.application.cache.tags import InMemoryTaggedCacheStore, TaggedCacheStore

__all__ = ["CacheWarmupService", "cached"]


def cached(
    ttl: int = 60,
    key_fn: Callable[..., str] | None = None,
    tags: list[str] | None = None,
    store: TaggedCacheStore | None = None,
):
    """Decorator: caches an async function's result in *store*.

    If no *store* is given, a module-level ``InMemoryTaggedCacheStore`` is used.
    *key_fn* receives the same args/kwargs as the wrapped function.
    """
    _store: TaggedCacheStore = store or InMemoryTaggedCacheStore()

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = key_fn(*args, **kwargs) if key_fn else f"{fn.__qualname__}:{args}:{sorted(kwargs.items())}"
            cached_val = await _store.get(key)
            if cached_val is not None:
                return cached_val
            result = await fn(*args, **kwargs)
            await _store.set(key, result, ttl=ttl, tags=tags)
            return result

        wrapper._cache_store = _store  # type: ignore[attr-defined]
        return wrapper

    return decorator


class CacheWarmupService:
    """Pre-populates cache entries before they expire."""

    def __init__(self, store: TaggedCacheStore) -> None:
        self._store = store
        self._loaders: dict[str, Callable[[], Awaitable[Any]]] = {}

    def register(self, key: str, loader: Callable[[], Awaitable[Any]]) -> None:
        self._loaders[key] = loader

    async def warm(self, key: str) -> Any:
        if key not in self._loaders:
            raise KeyError(f"No loader registered for key: {key!r}")
        value = await self._loaders[key]()
        await self._store.set(key, value, ttl=3600)
        return value
