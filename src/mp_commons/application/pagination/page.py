"""Application pagination – Page, CursorPage, Cursor."""
from __future__ import annotations

import dataclasses
import math
from typing import Any, Callable, Generic, TypeVar

from mp_commons.application.pagination.page_request import PageRequest

T = TypeVar("T")


@dataclasses.dataclass(frozen=True, slots=True)
class Cursor:
    """Cursor-based pagination token (opaque encoded string)."""
    value: str

    def __str__(self) -> str:
        return self.value


@dataclasses.dataclass
class Page(Generic[T]):
    """Offset-based page of results with computed navigation properties."""

    items: list[T]
    total: int
    page: int
    size: int

    @property
    def total_pages(self) -> int:
        if self.size <= 0 or self.total <= 0:
            return 0
        return math.ceil(self.total / self.size)

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    def map(self, fn: Callable[[T], Any]) -> "Page[Any]":
        """Return a new :class:`Page` with each item transformed by *fn*."""
        return Page(
            items=[fn(item) for item in self.items],
            total=self.total,
            page=self.page,
            size=self.size,
        )

    @classmethod
    def of(cls, all_items: list[T], request: PageRequest) -> "Page[T]":
        """Build a :class:`Page` by slicing *all_items* with *request*."""
        total = len(all_items)
        start = request.offset
        end = start + request.size
        return cls(
            items=all_items[start:end],
            total=total,
            page=request.page,
            size=request.size,
        )


@dataclasses.dataclass(frozen=True)
class CursorPage(Generic[T]):
    """Cursor-based page of results."""

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


__all__ = ["Cursor", "CursorPage", "Page"]
