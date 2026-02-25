"""Application cache – TaggedCacheStore and InMemory implementation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "CacheInvalidationEvent",
    "InMemoryTaggedCacheStore",
    "TaggedCacheStore",
]


@dataclass(frozen=True)
class CacheInvalidationEvent:
    """Emitted when a tag is invalidated."""
    tag: str
    keys_removed: int = 0


@runtime_checkable
class TaggedCacheStore(Protocol):
    async def set(self, key: str, value: Any, ttl: int, tags: list[str] | None = None) -> None: ...
    async def get(self, key: str) -> Any: ...
    async def delete(self, key: str) -> None: ...
    async def invalidate_tag(self, tag: str) -> int: ...  # returns number of removed keys


class InMemoryTaggedCacheStore:
    """In-memory TaggedCacheStore – for unit tests (no TTL enforcement)."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._tags: dict[str, set[str]] = {}   # tag -> {keys}
        self._key_tags: dict[str, set[str]] = {}  # key -> {tags}

    async def set(self, key: str, value: Any, ttl: int = 60, tags: list[str] | None = None) -> None:
        self._data[key] = value
        for tag in (tags or []):
            self._tags.setdefault(tag, set()).add(key)
            self._key_tags.setdefault(key, set()).add(tag)

    async def get(self, key: str) -> Any:
        return self._data.get(key)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
        for tag in self._key_tags.pop(key, set()):
            self._tags.get(tag, set()).discard(key)

    async def invalidate_tag(self, tag: str) -> int:
        keys = list(self._tags.pop(tag, set()))
        for key in keys:
            self._data.pop(key, None)
            self._key_tags.get(key, set()).discard(tag)
        return len(keys)
