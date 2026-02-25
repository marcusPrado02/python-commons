"""Application search – SearchEngine Protocol and InMemorySearchEngine."""
from __future__ import annotations

import time
from typing import Any, Callable, Generic, Protocol, TypeVar, runtime_checkable

from mp_commons.application.search.query import Filter, SearchQuery, SortField
from mp_commons.application.search.result import SearchResult

T = TypeVar("T")

__all__ = ["InMemorySearchEngine", "SearchEngine"]


@runtime_checkable
class SearchEngine(Protocol[T]):
    async def search(self, query: SearchQuery) -> SearchResult[T]: ...
    async def suggest(self, prefix: str, field: str) -> list[str]: ...


class InMemorySearchEngine(Generic[T]):
    """Full-text search engine that operates on a list of dict-like objects."""

    def __init__(self, items: list[T], key_fn: Callable[[T], dict[str, Any]] | None = None) -> None:
        self._items = items
        self._key_fn: Callable[[T], dict[str, Any]] = key_fn or (lambda x: x if isinstance(x, dict) else x.__dict__)

    def _matches_filter(self, item_dict: dict[str, Any], f: Filter) -> bool:
        val = item_dict.get(f.field)
        match f.op:
            case "eq":    return val == f.value
            case "neq":   return val != f.value
            case "gt":    return val is not None and val > f.value
            case "gte":   return val is not None and val >= f.value
            case "lt":    return val is not None and val < f.value
            case "lte":   return val is not None and val <= f.value
            case "in":    return val in f.value
            case "contains": return f.value in str(val or "")
            case _:       return True

    async def search(self, query: SearchQuery) -> SearchResult[T]:
        t0 = time.monotonic()
        results = []
        for item in self._items:
            d = self._key_fn(item)
            # text search
            if query.terms:
                text_match = any(
                    query.terms.lower() in str(v).lower()
                    for v in d.values()
                )
                if not text_match:
                    continue
            # filter
            if not all(self._matches_filter(d, f) for f in query.filters):
                continue
            results.append(item)

        # sort
        for sf in reversed(query.sort):
            results.sort(
                key=lambda x: self._key_fn(x).get(sf.field) or "",
                reverse=(sf.direction == "desc"),
            )

        total = len(results)
        start = (query.page - 1) * query.page_size
        page_items = results[start: start + query.page_size]
        took_ms = int((time.monotonic() - t0) * 1000)
        return SearchResult(
            items=page_items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            took_ms=took_ms,
        )

    async def suggest(self, prefix: str, field: str) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in self._items:
            val = str(self._key_fn(item).get(field, ""))
            if val.lower().startswith(prefix.lower()) and val not in seen:
                seen.add(val)
                out.append(val)
        return out
