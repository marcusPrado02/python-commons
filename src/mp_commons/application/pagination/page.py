"""Application pagination – Page, Cursor."""
from __future__ import annotations

import dataclasses
from typing import Generic, TypeVar

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
    """Single page of results."""
    items: list[T]
    total: int
    page: int
    size: int
    has_next: bool
    has_prev: bool
    next_cursor: Cursor | None = None

    @classmethod
    def of(cls, items: list[T], total: int, request: PageRequest) -> "Page[T]":
        return cls(
            items=items,
            total=total,
            page=request.page,
            size=request.size,
            has_next=request.offset + len(items) < total,
            has_prev=request.page > 1,
        )


__all__ = ["Cursor", "Page"]
