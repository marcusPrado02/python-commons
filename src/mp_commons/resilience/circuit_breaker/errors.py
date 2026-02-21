"""Resilience – circuit-breaker specific errors (§16.4)."""
from __future__ import annotations

from mp_commons.kernel.errors import InfrastructureError


class CircuitOpenError(InfrastructureError):
    """Raised when a :class:`CircuitBreaker` is in the OPEN state.

    Attributes
    ----------
    circuit_name:
        Name of the circuit breaker that rejected the call.
    """

    def __init__(self, circuit_name: str, message: str | None = None) -> None:
        self.circuit_name = circuit_name
        super().__init__(message or f"Circuit breaker '{circuit_name}' is OPEN")

    def to_dict(self) -> dict[str, str]:
        base = super().to_dict()
        base["circuit_name"] = self.circuit_name
        return base


__all__ = ["CircuitOpenError"]
