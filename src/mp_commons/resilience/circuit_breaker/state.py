"""Resilience – CircuitBreakerState enum."""
from __future__ import annotations
from enum import Enum


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


__all__ = ["CircuitBreakerState"]
