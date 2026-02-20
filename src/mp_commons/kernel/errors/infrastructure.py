"""Infrastructure errors — I/O failures, external integrations."""

from __future__ import annotations

from typing import Any

from mp_commons.kernel.errors.base import BaseError


class InfrastructureError(BaseError):
    """Infrastructure / I/O failure that is not a business rule violation."""

    default_code = "infrastructure_error"


class ConnectionError(InfrastructureError):  # noqa: A001
    """Failed to connect to an external resource (DB, broker, cache, …)."""

    default_code = "connection_error"

    def __init__(
        self,
        resource: str,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message or f"Could not connect to '{resource}'", **kwargs)
        self.resource = resource


class TimeoutError(InfrastructureError):  # noqa: A001
    """An I/O operation exceeded its deadline."""

    default_code = "infrastructure_timeout"


class SerializationError(InfrastructureError):
    """Failed to serialize or deserialize a payload."""

    default_code = "serialization_error"

    def __init__(
        self,
        message: str,
        *,
        payload_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.payload_type = payload_type


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
    "ConnectionError",
    "ExternalServiceError",
    "InfrastructureError",
    "SerializationError",
    "TimeoutError",
]
