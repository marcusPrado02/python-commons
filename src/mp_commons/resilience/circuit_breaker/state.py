"""Resilience – CircuitBreakerState enum."""
from __future__ import annotations
from enum import Enum


class CircuitBreakerState(str, Enum):
    """Finite states of a circuit breaker (CLOSED → OPEN → HALF_OPEN → CLOSED)."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


__all__ = ["CircuitBreakerState"]
