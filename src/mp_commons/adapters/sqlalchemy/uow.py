"""SQLAlchemy adapter – SqlAlchemyUnitOfWork."""
from __future__ import annotations

from typing import Any

from mp_commons.kernel.ddd import UnitOfWork


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy async unit of work."""

    def __init__(self, session_factory: Any) -> None:
        self._factory = session_factory
        self.session: Any = None

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._factory()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


__all__ = ["SqlAlchemyUnitOfWork"]
