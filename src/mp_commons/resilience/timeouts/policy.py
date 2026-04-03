"""Resilience – TimeoutPolicy."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import dataclasses
from typing import TypeVar

from mp_commons.kernel.errors import TimeoutError as AppTimeoutError

T = TypeVar("T")


@dataclasses.dataclass
class TimeoutPolicy:
    """Configuration for timeout enforcement."""

    timeout_seconds: float

    async def execute(self, func: Callable[[], Awaitable[T]]) -> T:
        try:
            return await asyncio.wait_for(func(), timeout=self.timeout_seconds)
        except TimeoutError as exc:
            raise AppTimeoutError(f"Operation timed out after {self.timeout_seconds}s") from exc


__all__ = ["TimeoutPolicy"]
