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
        if cause is not None:
            self.__cause__ = cause

    def __str__(self) -> str:
        """Return a JSON-serialisable single-line string representation."""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (safe for logging / HTTP responses)."""
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
        }
        if self.cause is not None:
            payload["cause"] = repr(self.cause)
        return payload


__all__ = ["BaseError"]
