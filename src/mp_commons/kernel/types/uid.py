"""ULID and UUIDv7 value objects."""

from __future__ import annotations

import base64
import dataclasses
import secrets
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


@dataclasses.dataclass(frozen=True, slots=True)
class UID:
    """12-character URL-safe base64 random identifier (stdlib only).

    Uses 9 random bytes (``secrets.token_bytes``) encoded as 12 URL-safe
    base64 characters — no padding, no external dependencies.

    Examples::

        uid = UID.generate()
        uid.value  # e.g. 'aB3-xQ7_kR2z'
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) != 12:  # noqa: PLR2004
            from mp_commons.kernel.errors.domain import ValidationError

            raise ValidationError(f"UID must be exactly 12 characters, got {len(self.value)}")

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> "UID":
        """Return a new cryptographically random 12-char URL-safe base64 ``UID``."""
        raw = secrets.token_bytes(9)  # 9 bytes → 12 base64 chars (no padding)
        return cls(base64.urlsafe_b64encode(raw).decode())


__all__ = ["ULID", "UID", "UUIDv7"]
