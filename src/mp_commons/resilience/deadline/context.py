from __future__ import annotations

import asyncio
import contextlib
from asyncio import TimeoutError as AsyncTimeoutError
from contextvars import ContextVar, Token
from typing import Any, Awaitable

from mp_commons.resilience.timeouts.deadline import Deadline

__all__ = [
    "DeadlineContext",
    "DeadlineExceededError",
    "deadline_aware",
]


class DeadlineExceededError(Exception):
    """Raised when the active deadline has been exceeded."""


_DEADLINE_VAR: ContextVar[Deadline | None] = ContextVar("_deadline", default=None)


class DeadlineContext:
    """Context-variable wrapper for propagating deadlines across async boundaries."""

    @staticmethod
    def set(deadline: Deadline) -> Token[Deadline | None]:
        return _DEADLINE_VAR.set(deadline)

    @staticmethod
    def get() -> Deadline | None:
        return _DEADLINE_VAR.get()

    @staticmethod
    def reset(token: Token[Deadline | None]) -> None:
        _DEADLINE_VAR.reset(token)

    @staticmethod
    def raise_if_exceeded() -> None:
        dl = _DEADLINE_VAR.get()
        if dl is not None and dl.is_expired:
            raise DeadlineExceededError("Deadline exceeded")

    @staticmethod
    @contextlib.asynccontextmanager
    async def scoped(deadline: Deadline):  # type: ignore[return]
        token = _DEADLINE_VAR.set(deadline)
        try:
            yield deadline
        finally:
            _DEADLINE_VAR.reset(token)


async def deadline_aware(coro: Awaitable[Any], deadline: Deadline | None = None) -> Any:
    """Wrap *coro* so it times out if the given (or context) deadline expires.

    Raises :class:`DeadlineExceededError` on timeout.
    """
    import inspect

    dl = deadline or _DEADLINE_VAR.get()
    if dl is None:
        return await coro
    remaining = dl.remaining_seconds
    if remaining <= 0:
        # Close the coroutine cleanly to avoid ResourceWarning
        if inspect.iscoroutine(coro):
            coro.close()
        raise DeadlineExceededError("Deadline already exceeded")
    try:
        return await asyncio.wait_for(asyncio.ensure_future(coro), timeout=remaining)
    except AsyncTimeoutError:
        raise DeadlineExceededError("Deadline exceeded during execution") from None
