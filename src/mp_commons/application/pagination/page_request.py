"""Application pagination – PageRequest, Sort, SortDirection, Filter."""
from __future__ import annotations

import dataclasses
from enum import Enum


class SortDirection(str, Enum):
    ASC = "ASC"
    DESC = "DESC"


@dataclasses.dataclass(frozen=True)
class Sort:
    """Single sort criterion."""
    field: str
    direction: SortDirection = SortDirection.ASC


@dataclasses.dataclass(frozen=True)
class Filter:
    """Key/value filter applied to a query."""
    field: str
    operator: str
    value: object


@dataclasses.dataclass(frozen=True)
class PageRequest:
    """Offset-based pagination parameters."""
    page: int = 1
    size: int = 20
    sorts: tuple[Sort, ...] = ()
    filters: tuple[Filter, ...] = ()

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if self.size < 1 or self.size > 1000:
            raise ValueError("size must be between 1 and 1000")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


__all__ = ["Filter", "PageRequest", "Sort", "SortDirection"]
