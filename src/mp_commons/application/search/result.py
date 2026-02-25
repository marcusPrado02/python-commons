"""Application search – SearchResult generic container."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")

__all__ = ["SearchResult"]


@dataclass
class SearchResult(Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    took_ms: int = 0
    highlights: dict[str, list[str]] = field(default_factory=dict)

    @property
    def total_pages(self) -> int:
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages
