"""E.164 phone number value object."""

from __future__ import annotations

import dataclasses
import re
from typing import Final

from mp_commons.kernel.errors.domain import ValidationError

_E164_PATTERN: Final = re.compile(r"^\+[1-9]\d{6,14}$")

# Minimal ITU country-calling-code length lookup (codes not in these sets are 3 digits).
_CC1: Final = frozenset({"1", "7"})
_CC2: Final = frozenset({
    "20", "27", "30", "31", "32", "33", "34", "36", "39",
    "40", "41", "43", "44", "45", "46", "47", "48", "49",
    "51", "52", "53", "54", "55", "56", "57", "58",
    "60", "61", "62", "63", "64", "65", "66",
    "81", "82", "84", "86",
    "90", "91", "92", "93", "94", "95", "98",
})


@dataclasses.dataclass(frozen=True, slots=True)
class PhoneNumber:
    """E.164 phone number value object."""

    value: str

    def __post_init__(self) -> None:
        if not _E164_PATTERN.match(self.value):
            raise ValidationError(f"Invalid E.164 phone number: {self.value!r}")

    def __str__(self) -> str:
        return self.value

    @property
    def country_code(self) -> str:
        """Return the ITU country calling code digits (no leading ``+``)."""
        digits = self.value[1:]  # strip leading +
        if digits[0] in _CC1:
            return digits[0]
        if digits[:2] in _CC2:
            return digits[:2]
        return digits[:3]

    @property
    def national_number(self) -> str:
        """Return the subscriber number without the country code."""
        return self.value[1 + len(self.country_code):]


__all__ = ["PhoneNumber"]
