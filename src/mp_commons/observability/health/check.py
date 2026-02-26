from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

__all__ = ["HealthCheck", "HealthStatus"]


@dataclass
class HealthStatus:
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
        start = time.monotonic()
        status = await self.check()
        status.latency_ms = (time.monotonic() - start) * 1000
        return status
