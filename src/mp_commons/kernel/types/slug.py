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

    @classmethod
    def from_text(cls, text: str) -> "Slug":
        """Normalise arbitrary text into a URL-safe slug.

        Rules applied in order:
        1. Lowercase + strip surrounding whitespace.
        2. Remove characters that are not word chars, spaces, or hyphens.
        3. Replace runs of whitespace/underscores with a single hyphen.
        4. Collapse consecutive hyphens.
        5. Strip leading/trailing hyphens.
        """
        value = text.lower().strip()
        value = re.sub(r"[^\w\s-]", "", value)
        value = re.sub(r"[\s_]+", "-", value)
        value = re.sub(r"-+", "-", value).strip("-")
        return cls(value)


__all__ = ["Slug"]
