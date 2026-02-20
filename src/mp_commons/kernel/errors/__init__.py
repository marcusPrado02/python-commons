"""Kernel error hierarchy — public re-export surface.

Hierarchy::

    BaseError
    ├── DomainError          (domain.py)
    │   ├── InvariantViolationError
    │   ├── ValidationError
    │   ├── NotFoundError
    │   └── ConflictError
    ├── ApplicationError     (application.py)
    │   ├── UnauthorizedError
    │   ├── ForbiddenError
    │   ├── RateLimitError
    │   └── TimeoutError
    └── InfrastructureError  (infrastructure.py)
        ├── ConnectionError
        ├── TimeoutError
        ├── SerializationError
        └── ExternalServiceError
"""

from mp_commons.kernel.errors.application import (
    ApplicationError,
    ForbiddenError,
    RateLimitError,
    TimeoutError,
    UnauthorizedError,
)
from mp_commons.kernel.errors.base import BaseError
from mp_commons.kernel.errors.domain import (
    ConflictError,
    DomainError,
    InvariantViolationError,
    NotFoundError,
    ValidationError,
)
from mp_commons.kernel.errors.infrastructure import (
    ConnectionError,
    ExternalServiceError,
    InfrastructureError,
    SerializationError,
)
from mp_commons.kernel.errors.infrastructure import TimeoutError as InfrastructureTimeoutError

__all__ = [
    "ApplicationError",
    "BaseError",
    "ConflictError",
    "ConnectionError",
    "DomainError",
    "ExternalServiceError",
    "ForbiddenError",
    "InfrastructureError",
    "InfrastructureTimeoutError",
    "InvariantViolationError",
    "NotFoundError",
    "RateLimitError",
    "SerializationError",
    "TimeoutError",
    "UnauthorizedError",
    "ValidationError",
]
