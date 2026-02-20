"""Resilience – CircuitBreakerPolicy."""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class CircuitBreakerPolicy:
    """Configuration for a circuit breaker."""
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 30.0
    window_seconds: float = 60.0
    excluded_exceptions: tuple[type[Exception], ...] = ()


__all__ = ["CircuitBreakerPolicy"]
