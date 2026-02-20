"""Unit of Work port — transactional boundary."""

from __future__ import annotations

import abc
from typing import Any


class UnitOfWork(abc.ABC):
    """Port: transactional unit of work."""

    @abc.abstractmethod
    async def commit(self) -> None: ...

    @abc.abstractmethod
    async def rollback(self) -> None: ...

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()


__all__ = ["UnitOfWork"]
