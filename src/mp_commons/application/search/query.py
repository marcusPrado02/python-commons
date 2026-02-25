"""Application search – SearchQuery value object."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

__all__ = ["Filter", "SearchQuery", "SortField"]


@dataclass(frozen=True)
class Filter:
    """A field-level filter applied to search results."""
    field: str
    value: Any
    op: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "contains"] = "eq"


@dataclass(frozen=True)
class SortField:
    field: str
    direction: Literal["asc", "desc"] = "asc"


@dataclass
class SearchQuery:
    terms: str = ""
    filters: list[Filter] = field(default_factory=list)
    sort: list[SortField] = field(default_factory=list)
    page: int = 1
    page_size: int = 20
    highlight_fields: list[str] = field(default_factory=list)
