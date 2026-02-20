"""Domain errors — business rule and invariant violations."""

from __future__ import annotations

from typing import Any

from mp_commons.kernel.errors.base import BaseError


class DomainError(BaseError):
    """Raised when a domain rule / invariant is violated."""

    default_code = "domain_error"


class InvariantViolationError(DomainError):
    """An aggregate invariant was violated."""

    default_code = "invariant_violation"


class ValidationError(DomainError):
    """Input data does not meet validation rules.

    ``errors`` is a list of field-level validation failures.
    """

    default_code = "validation_error"

    def __init__(
        self,
        message: str,
        *,
        errors: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.errors: list[dict[str, Any]] = errors or []

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["errors"] = self.errors
        return base


class NotFoundError(DomainError):
    """The requested resource does not exist."""

    default_code = "not_found"

    def __init__(
        self,
        resource: str,
        identifier: Any = None,
        **kwargs: Any,
    ) -> None:
        msg = f"{resource} not found"
        if identifier is not None:
            msg = f"{resource} '{identifier}' not found"
        super().__init__(msg, **kwargs)
        self.resource = resource
        self.identifier = identifier


class ConflictError(DomainError):
    """The operation conflicts with existing state."""

    default_code = "conflict"


__all__ = [
    "ConflictError",
    "DomainError",
    "InvariantViolationError",
    "NotFoundError",
    "ValidationError",
]
