"""Resilience – jitter strategies."""
from __future__ import annotations

import abc
import random


class JitterStrategy(abc.ABC):
    """Apply randomness to a backoff delay to spread thundering-herd."""

    @abc.abstractmethod
    def apply(self, delay: float) -> float: ...


class NoJitter(JitterStrategy):
    def apply(self, delay: float) -> float:
        return delay


class FullJitter(JitterStrategy):
    """Uniform random in [0, delay]."""

    def apply(self, delay: float) -> float:
        return random.uniform(0, delay)


class EqualJitter(JitterStrategy):
    """Uniform random in [delay/2, delay]."""

    def apply(self, delay: float) -> float:
        half = delay / 2
        return half + random.uniform(0, half)


__all__ = ["EqualJitter", "FullJitter", "JitterStrategy", "NoJitter"]
