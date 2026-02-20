"""Infrastructure errors — I/O failures, external integrations."""

from __future__ import annotations

from typing import Any

from mp_commons.kernel.errors.base import BaseError


class InfrastructureError(BaseError):
    """Infrastructure / I/O failure that is not a business rule violation."""

    default_code = "infrastructure_error"


class ExternalServiceError(InfrastructureError):
    """An external service returned an unexpected response."""

    default_code = "external_service_error"

    def __init__(
        self,
        service: str,
        message: str | None = None,
        *,
        status_code: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message or f"External service '{service}' error", **kwargs)
        self.service = service
        self.status_code = status_code


__all__ = [
    "ExternalServiceError",
    "InfrastructureError",
]
