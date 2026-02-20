"""URL-safe slug value object."""

from __future__ import annotations

import dataclasses
import re
from typing import Final

from mp_commons.kernel.errors.domain import ValidationError

_SLUG_PATTERN: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclasses.dataclass(frozen=True, slots=True)
class Slug:
    """URL-safe lowercase slug."""

    value: str

    def __post_init__(self) -> None:
        if not _SLUG_PATTERN.match(self.value):
            raise ValidationError(
                f"Invalid slug (must be lowercase alphanumeric + hyphens): {self.value!r}"
            )

    def __str__(self) -> str:
        return self.value


__all__ = ["Slug"]
