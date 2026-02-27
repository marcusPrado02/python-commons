"""Unit tests for §94 – Database Fixtures."""
from __future__ import annotations

import asyncio

import pytest

from mp_commons.testing.fixtures.database import DatabaseFixture, TransactionalTestSession


class TestDatabaseFixture:
    def test_setup_and_teardown(self):
        """DatabaseFixture should run create_all and drop_all on the engine."""
        create_calls = []
        drop_calls = []

        class _FakeMeta:
            def create_all(self, conn):
                create_calls.append(conn)

            def drop_all(self, conn):
                drop_calls.append(conn)

        class _FakeBase:
            metadata = _FakeMeta()

        class _FakeConn:
            async def run_sync(self, fn):
                fn(self)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        class _FakeEngine:
            def begin(self):
                return _FakeConn()

        fixture = DatabaseFixture(_FakeBase())
        asyncio.run(fixture.setup(_FakeEngine()))
        assert len(create_calls) == 1

        asyncio.run(fixture.teardown(_FakeEngine()))
        assert len(drop_calls) == 1

    def test_fixture_accepts_custom_base(self):
        class _Base:
            class metadata:
                @staticmethod
                def create_all(conn): pass
                @staticmethod
                def drop_all(conn): pass

        fixture = DatabaseFixture(_Base)
        assert fixture._base is _Base


class TestTransactionalTestSessionImports:
    def test_import_succeeds(self):
        from mp_commons.testing.fixtures.database import (  # noqa
            TransactionalTestSession,
            db_fixture,
        )

    def test_db_fixture_requires_pytest(self):
        from mp_commons.testing.fixtures.database import db_fixture  # noqa
        # Should not crash on import; actual fixture creation needs pytest


class TestDbFixtureIntegration:
    """Lightweight integration: use aiosqlite + SQLAlchemy in-memory."""

    def test_sqlite_async_setup_teardown(self):
        try:
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy.orm import DeclarativeBase
            from sqlalchemy import Column, Integer, String
        except ImportError:
            pytest.skip("sqlalchemy not available")

        class Base(DeclarativeBase):
            pass

        class _Item(Base):
            __tablename__ = "items"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        async def run():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            fixture = DatabaseFixture(Base)
            await fixture.setup(engine)
            # Verify table exists by inserting
            from sqlalchemy.ext.asyncio import AsyncSession
            async with AsyncSession(engine) as session:
                session.add(_Item(id=1, name="hello"))
                await session.commit()
            await fixture.teardown(engine)
            await engine.dispose()

        asyncio.run(run())
