"""Application UoW – transactional decorator."""
from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

from mp_commons.kernel.ddd import UnitOfWork

F = TypeVar("F", bound=Callable[..., Any])


def transactional(uow_attribute: str = "_uow") -> Callable[[F], F]:
    """Decorator: wrap an async method in a UoW transaction."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            uow: UnitOfWork | None = getattr(self, uow_attribute, None)
            if uow is None:
                return await func(self, *args, **kwargs)
            async with uow:
                return await func(self, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["transactional"]
