"""MongoDB adapter — MongoUnitOfWork."""

from __future__ import annotations

from typing import Any

from mp_commons.kernel.ddd import UnitOfWork


class MongoUnitOfWork(UnitOfWork):
    """Unit of work backed by a **motor** client session.

    Requires a MongoDB replica set (or a transaction-capable topology) to
    support multi-document ACID transactions.  On a standalone instance
    :meth:`commit` and :meth:`rollback` are no-ops at the storage level
    (the session is still closed cleanly).

    Usage::

        async with MongoUnitOfWork(motor_client) as uow:
            await some_repo.save(aggregate, session=uow.session)
    """

    def __init__(self, client: Any) -> None:
        self._client = client
        self.session: Any = None

    async def __aenter__(self) -> "MongoUnitOfWork":
        self.session = await self._client.start_session()
        self.session.start_transaction()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        try:
            if exc_type is None:
                await self.commit()
            else:
                await self.rollback()
        finally:
            await self.session.end_session()

    async def commit(self) -> None:
        """Commit the active MongoDB transaction."""
        await self.session.commit_transaction()

    async def rollback(self) -> None:
        """Abort the active MongoDB transaction."""
        await self.session.abort_transaction()


__all__ = ["MongoUnitOfWork"]
