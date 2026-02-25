"""Application scheduler – Job dataclass."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

__all__ = ["Job"]


@dataclass
class Job:
    """Describes a scheduled job."""

    id: str
    name: str
    handler: Callable[[], Awaitable[None]]
    cron: str | None = None          # e.g. "0 9 * * MON"
    interval_seconds: int | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.cron is None and self.interval_seconds is None:
            raise ValueError("Job must have either 'cron' or 'interval_seconds'")
        if self.cron is not None and self.interval_seconds is not None:
            raise ValueError("Job cannot have both 'cron' and 'interval_seconds'")
