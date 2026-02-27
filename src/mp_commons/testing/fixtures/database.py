"""Database testing fixtures: DatabaseFixture, TransactionalTestSession, db_fixture."""
from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Callable, Type

__all__ = [
    "DatabaseFixture",
    "TransactionalTestSession",
    "db_fixture",
]


class DatabaseFixture:
    """Create and drop all SQLAlchemy tables for test isolation."""

    def __init__(self, base: Any) -> None:
        self._base = base

    async def setup(self, engine: Any) -> None:
        """Create all tables in the DB bound to *engine*."""
        async with engine.begin() as conn:
            await conn.run_sync(self._base.metadata.create_all)

    async def teardown(self, engine: Any) -> None:
        """Drop all tables in the DB bound to *engine*."""
        async with engine.begin() as conn:
            await conn.run_sync(self._base.metadata.drop_all)


class TransactionalTestSession:
    """Wraps an AsyncSession in a SAVEPOINT; rolls back after each test.

    Usage::

        async def test_something(transactional_session):
            session = await TransactionalTestSession.create(engine)
            # ... use session ...
            await session.rollback()
    """

    def __init__(self, session: Any, savepoint: Any) -> None:
        self._session = session
        self._savepoint = savepoint

    @property
    def session(self) -> Any:
        return self._session

    @classmethod
    async def create(cls, engine: Any) -> TransactionalTestSession:
        try:
            from sqlalchemy.ext.asyncio import AsyncSession
        except ImportError as exc:
            raise ImportError("pip install sqlalchemy[asyncio]") from exc

        conn = await engine.connect()
        trans = await conn.begin()
        session = AsyncSession(bind=conn)
        nested = await conn.begin_nested()  # SAVEPOINT
        return cls(session=session, savepoint=conn)

    async def rollback(self) -> None:
        await self._session.close()
        await self._savepoint.rollback()
        await self._savepoint.close()


def db_fixture(engine_factory: Callable[[], Any]) -> Any:
    """Decorator that builds a pytest fixture yielding a TransactionalTestSession.

    Usage::

        @db_fixture(lambda: create_async_engine(...))
        async def db_session():
            ...
    """
    try:
        import pytest
    except ImportError as exc:
        raise ImportError("pip install pytest") from exc

    def decorator(fn: Any) -> Any:
        @pytest.fixture
        async def _fixture() -> AsyncGenerator[TransactionalTestSession, None]:
            engine = engine_factory()
            ts = await TransactionalTestSession.create(engine)
            try:
                yield ts
            finally:
                await ts.rollback()
                await engine.dispose()

        _fixture.__name__ = fn.__name__
        return _fixture

    return decorator
