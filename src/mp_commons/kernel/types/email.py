"""Email address value object."""

from __future__ import annotations

import dataclasses
import re
from typing import Any, Final

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

    @property
    def domain(self) -> str:
        """Return the domain portion of the address (everything after ``@``)."""
        return self.value.split("@", 1)[1]

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: Any,
    ) -> Any:
        try:
            from pydantic_core import core_schema

            return core_schema.no_info_plain_validator_function(
                lambda v: cls(v) if isinstance(v, str) else v,
                serialization=core_schema.to_string_ser_schema(),
            )
        except ImportError:
            raise


__all__ = ["Email"]
