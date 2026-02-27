"""Deterministic JSON serialiser for snapshot testing."""
from __future__ import annotations

import dataclasses
import enum
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

__all__ = ["SnapshotSerializer"]


class _SnapshotEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:  # noqa: ANN001
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, enum.Enum):
            return obj.value
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


class SnapshotSerializer:
    """Serialise arbitrary values to a deterministic JSON string."""

    def __init__(self, indent: int = 2) -> None:
        self._indent = indent

    def serialize(self, value: Any) -> str:
        return json.dumps(value, cls=_SnapshotEncoder, indent=self._indent, sort_keys=True)
