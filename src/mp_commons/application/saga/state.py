"""Application saga – SagaState enum."""

from __future__ import annotations

import enum


class SagaState(enum.Enum):
    """Lifecycle states of a saga execution."""

    RUNNING = "RUNNING"
    """Saga is currently executing forward steps."""

    COMPLETED = "COMPLETED"
    """All steps completed successfully."""

    COMPENSATING = "COMPENSATING"
    """A step failed; compensations are running in reverse order."""

    COMPENSATION_FAILED = "COMPENSATION_FAILED"
    """At least one compensation step also raised an exception."""

    FAILED = "FAILED"
    """A step failed and all compensations finished without error."""


__all__ = ["SagaState"]
