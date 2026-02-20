"""Application-layer errors — cross-cutting concerns at use-case level."""

from __future__ import annotations

from typing import Any

from mp_commons.kernel.errors.base import BaseError


class ApplicationError(BaseError):
    """Cross-cutting application-layer concern."""

    default_code = "application_error"


class UnauthorizedError(ApplicationError):
    """Missing or invalid credentials."""

    default_code = "unauthorized"


class ForbiddenError(ApplicationError):
    """Authenticated principal lacks required permission."""

    default_code = "forbidden"

    def __init__(
        self,
        message: str = "Access denied",
        *,
        permission: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.permission = permission


class RateLimitError(ApplicationError):
    """Request quota exceeded."""

    default_code = "rate_limit_exceeded"

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after_seconds: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class TimeoutError(ApplicationError):  # noqa: A001
    """Operation timed out."""

    default_code = "timeout"


__all__ = [
    "ApplicationError",
    "ForbiddenError",
    "RateLimitError",
    "TimeoutError",
    "UnauthorizedError",
]
