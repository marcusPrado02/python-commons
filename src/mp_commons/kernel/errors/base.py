"""Root error class for the mp-commons error hierarchy."""

from __future__ import annotations

from typing import Any


class BaseError(Exception):
    """Root of the error hierarchy.

    Args:
        message: Human-readable description.
        code: Machine-readable slug (defaults to class name snake_case).
        detail: Arbitrary extra context (serialisable dict).
        cause: Original exception that triggered this error.
    """

    default_code: str = "base_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        detail: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.detail: dict[str, Any] = detail or {}
        self.cause = cause

    def __repr__(self) -> str:  # pragma: no cover
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (safe for logging / HTTP responses)."""
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
        }


__all__ = ["BaseError"]
