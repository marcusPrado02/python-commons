from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import time

__all__ = ["HealthCheck", "HealthStatus"]


@dataclass
class HealthStatus:
    """Result of a single health check probe."""

    healthy: bool
    detail: str | None = None
    latency_ms: float = 0.0


class HealthCheck(ABC):
    """Base class for all health checks."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def check(self) -> HealthStatus: ...

    async def timed_check(self) -> HealthStatus:
        """Run :meth:`check` and populate ``latency_ms`` on the returned status."""
        start = time.monotonic()
        status = await self.check()
        status.latency_ms = (time.monotonic() - start) * 1000
        return status
