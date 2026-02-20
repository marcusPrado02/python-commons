"""Resilience – backoff strategies."""
from __future__ import annotations

import abc


class BackoffStrategy(abc.ABC):
    """Compute wait duration (seconds) after the *attempt*-th failure."""

    @abc.abstractmethod
    def compute(self, attempt: int) -> float: ...


class ConstantBackoff(BackoffStrategy):
    """Fixed delay between attempts."""

    def __init__(self, delay: float = 1.0) -> None:
        self._delay = delay

    def compute(self, attempt: int) -> float:  # noqa: ARG002
        return self._delay


class LinearBackoff(BackoffStrategy):
    """Delay grows linearly: ``base_delay * attempt``."""

    def __init__(self, base_delay: float = 0.5, max_delay: float = 30.0) -> None:
        self._base = base_delay
        self._max = max_delay

    def compute(self, attempt: int) -> float:
        return min(self._base * attempt, self._max)


class ExponentialBackoff(BackoffStrategy):
    """Delay grows exponentially: ``base_delay * 2^attempt``."""

    def __init__(self, base_delay: float = 0.1, max_delay: float = 30.0) -> None:
        self._base = base_delay
        self._max = max_delay

    def compute(self, attempt: int) -> float:
        return min(self._base * (2 ** attempt), self._max)


__all__ = ["BackoffStrategy", "ConstantBackoff", "ExponentialBackoff", "LinearBackoff"]
