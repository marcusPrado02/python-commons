"""Application UoW – TransactionManager port."""
from __future__ import annotations

import abc


class TransactionManager(abc.ABC):
    """Port: manage transaction lifecycle (begin/commit/rollback)."""

    @abc.abstractmethod
    async def begin(self) -> None: ...

    @abc.abstractmethod
    async def commit(self) -> None: ...

    @abc.abstractmethod
    async def rollback(self) -> None: ...


__all__ = ["TransactionManager"]
