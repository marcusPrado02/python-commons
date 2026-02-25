"""Application export – ExportRequest and ColumnDef."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Literal

__all__ = ["ColumnDef", "ExportRequest"]


@dataclass(frozen=True)
class ColumnDef:
    """Defines a single column in an export."""

    key: str          # dict key to read from each row
    header: str       # column header text
    format: str = ""  # optional format hint, e.g. "date", "currency"


@dataclass
class ExportRequest:
    """Describes a data export to be performed."""

    columns: list[ColumnDef]
    rows: AsyncIterator[dict]
    format: Literal["csv", "xlsx", "json"]
    filename: str = "export"
