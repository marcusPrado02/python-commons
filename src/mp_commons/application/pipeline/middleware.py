"""Application pipeline – Middleware base."""

from __future__ import annotations

import abc
from collections.abc import Awaitable, Callable
from typing import Any

Handler = Callable[[Any], Awaitable[Any]]
Next = Callable[[Any], Awaitable[Any]]


class Middleware(abc.ABC):
    """Single node in the middleware chain."""

    @abc.abstractmethod
    async def __call__(self, request: Any, next_: Next) -> Any: ...


__all__ = ["Handler", "Middleware", "Next"]
