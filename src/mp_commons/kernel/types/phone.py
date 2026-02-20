"""E.164 phone number value object."""

from __future__ import annotations

import dataclasses
import re
from typing import Final

from mp_commons.kernel.errors.domain import ValidationError

_E164_PATTERN: Final = re.compile(r"^\+[1-9]\d{6,14}$")


@dataclasses.dataclass(frozen=True, slots=True)
class PhoneNumber:
    """E.164 phone number value object."""

    value: str

    def __post_init__(self) -> None:
        if not _E164_PATTERN.match(self.value):
            raise ValidationError(f"Invalid E.164 phone number: {self.value!r}")

    def __str__(self) -> str:
        return self.value


__all__ = ["PhoneNumber"]
