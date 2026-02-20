"""Email address value object."""

from __future__ import annotations

import dataclasses
import re
from typing import Final

from mp_commons.kernel.errors.domain import ValidationError

_EMAIL_PATTERN: Final = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


@dataclasses.dataclass(frozen=True, slots=True)
class Email:
    """RFC-5321 email address value object (normalised to lowercase)."""

    value: str

    def __post_init__(self) -> None:
        normalised = self.value.lower().strip()
        object.__setattr__(self, "value", normalised)
        if not _EMAIL_PATTERN.match(normalised):
            raise ValidationError(f"Invalid email address: {self.value!r}")

    def __str__(self) -> str:
        return self.value


__all__ = ["Email"]
