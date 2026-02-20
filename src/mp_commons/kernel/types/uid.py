"""ULID and UUIDv7 value objects."""

from __future__ import annotations

import dataclasses
import uuid

from mp_commons.kernel.errors.domain import ValidationError

_ULID_RE_VALUE = r"^[0-9A-HJKMNP-TV-Z]{26}$"


@dataclasses.dataclass(frozen=True, slots=True)
class ULID:
    """ULID as an immutable value object.

    Pass an existing ULID string, or call ``ULID.generate()`` to create a new
    one (requires the ``python-ulid`` package at runtime).
    """

    value: str

    def __post_init__(self) -> None:
        import re
        if not re.match(_ULID_RE_VALUE, self.value.upper()):
            raise ValidationError(f"Invalid ULID: {self.value!r}")

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> "ULID":
        try:
            from ulid import ULID as _ULID  # type: ignore[import-untyped]
            return cls(str(_ULID()))
        except ImportError as exc:
            raise ImportError("Install 'python-ulid' to generate ULIDs") from exc


@dataclasses.dataclass(frozen=True, slots=True)
class UUIDv7:
    """UUID version 7 as an immutable value object."""

    value: uuid.UUID

    def __post_init__(self) -> None:
        if self.value.version != 7:
            raise ValidationError(f"Expected UUID v7, got v{self.value.version}")

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def generate(cls) -> "UUIDv7":
        try:
            import uuid_utils  # type: ignore[import-untyped]
            return cls(uuid.UUID(str(uuid_utils.uuid7())))
        except ImportError as exc:
            raise ImportError("Install 'uuid-utils' to generate UUIDv7") from exc


__all__ = ["ULID", "UUIDv7"]
