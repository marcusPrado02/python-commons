"""ValueObject base class."""

from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass(frozen=True)
class ValueObject:
    """Base class for value objects.

    Subclasses should be ``@dataclass(frozen=True)``.  Equality and hashing
    are based on field values (dataclass default for frozen).
    """

    def _validate(self) -> None:
        """Override to add cross-field invariant checks."""

    def copy_with(self, **changes: Any) -> "ValueObject":
        """Return a new instance with given fields replaced."""
        return dataclasses.replace(self, **changes)  # type: ignore[type-var]


__all__ = ["ValueObject"]
