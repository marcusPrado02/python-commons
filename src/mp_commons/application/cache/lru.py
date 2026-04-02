"""Async in-process LRU cache with TTL support (P-04).

:class:`AsyncLRUCache` provides a lightweight, asyncio-safe LRU cache backed
by ``collections.OrderedDict``.  Unlike Redis-based caches it has zero network
overhead and is best suited for **low-cardinality, read-heavy, short-lived**
values such as feature flags, config snapshots, or user permissions.

Usage::

    cache = AsyncLRUCache(maxsize=512, ttl=60.0)


    async def get_permissions(user_id: str) -> list[str]:
        cached = await cache.get(user_id)
        if cached is not None:
            return cached
        perms = await db.fetch_permissions(user_id)
        await cache.set(user_id, perms)
        return perms


    # Or with the get_or_load helper:
    perms = await cache.get_or_load(user_id, loader=db.fetch_permissions)
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Callable, Coroutine
import time
from typing import Any, TypeVar

_T = TypeVar("_T")

_SENTINEL = object()


class AsyncLRUCache:
    """Asyncio-safe in-process LRU cache with optional per-entry TTL.

    Parameters
    ----------
    maxsize:
        Maximum number of entries to keep in the cache.  When full the
        least recently used entry is evicted.  Must be ≥ 1.
    ttl:
        Optional time-to-live in seconds for each entry.  Entries that
        have not been accessed within *ttl* seconds are treated as
        expired and evicted lazily on next access.  ``None`` means no
        TTL (entries live until evicted by the LRU policy).
    """

    def __init__(self, maxsize: int = 256, ttl: float | None = None) -> None:
        if maxsize < 1:
            raise ValueError(f"maxsize must be >= 1, got {maxsize}")
        self._maxsize = maxsize
        self._ttl = ttl
        self._store: OrderedDict[Any, tuple[Any, float | None]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    def ttl(self) -> float | None:
        return self._ttl

    @property
    def size(self) -> int:
        """Current number of entries (including potentially expired ones)."""
        return len(self._store)

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def get(self, key: Any) -> Any | None:
        """Return the cached value for *key*, or ``None`` if absent/expired."""
        async with self._lock:
            entry = self._store.get(key, _SENTINEL)
            if entry is _SENTINEL:
                self._misses += 1
                return None
            value, expires_at = entry  # type: ignore[misc]
            if expires_at is not None and time.monotonic() > expires_at:  # type: ignore[has-type]
                del self._store[key]
                self._misses += 1
                return None
            # Move to end (most recently used)
            self._store.move_to_end(key)
            self._hits += 1
            return value  # type: ignore[has-type]

    async def set(self, key: Any, value: Any, ttl: float | None = None) -> None:
        """Store *value* under *key*.

        Parameters
        ----------
        key:
            Cache key (must be hashable).
        value:
            Value to store.
        ttl:
            Per-entry TTL override in seconds.  ``None`` uses the cache-level
            TTL configured at construction time.
        """
        effective_ttl = ttl if ttl is not None else self._ttl
        expires_at = time.monotonic() + effective_ttl if effective_ttl is not None else None
        async with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, expires_at)
            if len(self._store) > self._maxsize:
                self._store.popitem(last=False)  # evict LRU entry

    async def delete(self, key: Any) -> bool:
        """Remove *key* from the cache.  Returns ``True`` if it was present."""
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> None:
        """Remove all entries from the cache."""
        async with self._lock:
            self._store.clear()

    async def get_or_load(
        self,
        key: Any,
        loader: Callable[..., Any] | Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        ttl: float | None = None,
        **kwargs: Any,
    ) -> Any:
        """Return the cached value for *key*, loading it via *loader* on miss.

        The loader is called with ``*args`` and ``**kwargs`` when the key is
        absent or expired.  Both sync and async loaders are accepted.

        Parameters
        ----------
        key:
            Cache key.
        loader:
            Callable ``(*args, **kwargs) -> T`` (sync or async) used to load
            the value on cache miss.
        ttl:
            Per-entry TTL override; falls back to cache-level TTL.

        Example::

            value = await cache.get_or_load(
                user_id,
                loader=fetch_user_from_db,
                ttl=300.0,
            )
        """
        cached = await self.get(key)
        if cached is not None:
            return cached
        result = loader(*args, **kwargs)
        if asyncio.iscoroutine(result):
            result = await result
        await self.set(key, result, ttl=ttl)
        return result

    def __repr__(self) -> str:
        return (
            f"AsyncLRUCache(maxsize={self._maxsize}, ttl={self._ttl}, "
            f"size={self.size}, hits={self._hits}, misses={self._misses})"
        )


__all__ = ["AsyncLRUCache"]
