"""Integration tests for SQLAlchemy adapters – Postgres (§27.7).

Uses testcontainers to spawn a real PostgreSQL instance.
Run with: PYTHONPATH=src pytest tests/integration/test_postgres.py -m integration -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from testcontainers.postgres import PostgresContainer

from mp_commons.adapters.sqlalchemy import (
    SqlAlchemyOutboxRepository,
    SqlAlchemySessionFactory,
    SqlAlchemyUnitOfWork,
)
from mp_commons.kernel.messaging import OutboxRecord, OutboxStatus


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def _pg_url(container: Any) -> str:
    """Return an asyncpg-compatible URL from a PostgresContainer."""
    raw = container.get_connection_url()
    # testcontainers returns psycopg2 URL; swap driver for asyncpg
    return raw.replace("psycopg2", "asyncpg", 1)


# ---------------------------------------------------------------------------
# Outbox model factory (Core Table approach, no ORM dependency)
# ---------------------------------------------------------------------------

def _make_outbox_model() -> Any:  # noqa: ANN401
    """
    Dynamically create a SQLAlchemy ORM model for the outbox table.
    Uses the classic Column approach (no Mapped[] annotations) to avoid
    annotation-resolution issues inside function scope.
    """
    from sqlalchemy import (  # type: ignore[import-untyped]
        Column,
        DateTime,
        JSON,
        LargeBinary,
        String,
        Text,
    )
    from sqlalchemy.orm import DeclarativeBase  # type: ignore[import-untyped]

    class Base(DeclarativeBase):
        pass

    class OutboxRecordModel(Base):
        __tablename__ = "outbox_records"

        id = Column(String(36), primary_key=True)
        aggregate_id = Column(String(256), nullable=False)
        aggregate_type = Column(String(256), nullable=False)
        event_type = Column(String(256), nullable=False)
        topic = Column(String(256), nullable=False)
        payload = Column(LargeBinary, nullable=False)
        headers = Column(JSON, nullable=True)
        status = Column(String(32), nullable=False)
        created_at = Column(DateTime(timezone=True), nullable=False)
        dispatched_at = Column(DateTime(timezone=True), nullable=True)
        last_error = Column(Text, nullable=True)

    return Base, OutboxRecordModel


async def _create_tables(engine: Any, base: Any) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)


# ---------------------------------------------------------------------------
# §27.7 – SqlAlchemyUnitOfWork commit / rollback
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSqlAlchemyUoWIntegration:
    """Real Postgres UnitOfWork tests."""

    def test_uow_commit_persists_outbox_record(self) -> None:
        with PostgresContainer("postgres:16-alpine") as container:
            url = _pg_url(container)

            async def run() -> None:
                factory = SqlAlchemySessionFactory(url)
                Base, Model = _make_outbox_model()
                await _create_tables(factory._engine, Base)  # noqa: SLF001

                record = OutboxRecord(
                    aggregate_id="agg-1",
                    aggregate_type="Order",
                    event_type="OrderPlaced",
                    topic="orders",
                    payload=b'{"order_id": "1"}',
                )

                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    await repo.save(record)

                # Verify in a fresh session
                async with SqlAlchemyUnitOfWork(factory) as uow2:
                    repo2 = SqlAlchemyOutboxRepository(uow2.session, Model)
                    pending = await repo2.get_pending()
                    assert len(pending) == 1
                    assert pending[0].aggregate_id == "agg-1"

                await factory._engine.dispose()  # noqa: SLF001

            _run(run())

    def test_uow_rollback_on_exception(self) -> None:
        with PostgresContainer("postgres:16-alpine") as container:
            url = _pg_url(container)

            async def run() -> None:
                factory = SqlAlchemySessionFactory(url)
                Base, Model = _make_outbox_model()
                await _create_tables(factory._engine, Base)  # noqa: SLF001

                record = OutboxRecord(
                    aggregate_id="agg-2",
                    aggregate_type="Order",
                    event_type="OrderPlaced",
                    topic="orders",
                    payload=b"{}",
                )

                with pytest.raises(ValueError, match="force rollback"):
                    async with SqlAlchemyUnitOfWork(factory) as uow:
                        repo = SqlAlchemyOutboxRepository(uow.session, Model)
                        await repo.save(record)
                        raise ValueError("force rollback")

                # Nothing should be in the DB
                async with SqlAlchemyUnitOfWork(factory) as uow2:
                    repo2 = SqlAlchemyOutboxRepository(uow2.session, Model)
                    pending = await repo2.get_pending()
                    assert len(pending) == 0

                await factory._engine.dispose()  # noqa: SLF001

            _run(run())

    def test_uow_multiple_commits_accumulate(self) -> None:
        with PostgresContainer("postgres:16-alpine") as container:
            url = _pg_url(container)

            async def run() -> None:
                factory = SqlAlchemySessionFactory(url)
                Base, Model = _make_outbox_model()
                await _create_tables(factory._engine, Base)  # noqa: SLF001

                for i in range(3):
                    async with SqlAlchemyUnitOfWork(factory) as uow:
                        repo = SqlAlchemyOutboxRepository(uow.session, Model)
                        rec = OutboxRecord(
                            aggregate_id=f"agg-{i}",
                            aggregate_type="Order",
                            event_type="OrderPlaced",
                            topic="orders",
                            payload=b"{}",
                        )
                        await repo.save(rec)

                async with SqlAlchemyUnitOfWork(factory) as uow2:
                    repo2 = SqlAlchemyOutboxRepository(uow2.session, Model)
                    pending = await repo2.get_pending()
                    assert len(pending) == 3

                await factory._engine.dispose()  # noqa: SLF001

            _run(run())


# ---------------------------------------------------------------------------
# §27.7 – SqlAlchemyOutboxRepository lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSqlAlchemyOutboxRepositoryIntegration:
    """Real Postgres outbox lifecycle tests."""

    def test_get_pending_returns_pending_records_only(self) -> None:
        with PostgresContainer("postgres:16-alpine") as container:
            url = _pg_url(container)

            async def run() -> None:
                factory = SqlAlchemySessionFactory(url)
                Base, Model = _make_outbox_model()
                await _create_tables(factory._engine, Base)  # noqa: SLF001

                # Save two records, then dispatch one
                rec1 = OutboxRecord(aggregate_id="a1", aggregate_type="X", event_type="E", topic="t", payload=b"{}")
                rec2 = OutboxRecord(aggregate_id="a2", aggregate_type="X", event_type="E", topic="t", payload=b"{}")

                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    await repo.save(rec1)
                    await repo.save(rec2)

                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    await repo.mark_dispatched(rec1.id)

                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    pending = await repo.get_pending()
                    assert len(pending) == 1
                    assert pending[0].aggregate_id == "a2"

                await factory._engine.dispose()  # noqa: SLF001

            _run(run())

    def test_mark_dispatched_updates_status(self) -> None:
        with PostgresContainer("postgres:16-alpine") as container:
            url = _pg_url(container)

            async def run() -> None:
                factory = SqlAlchemySessionFactory(url)
                Base, Model = _make_outbox_model()
                await _create_tables(factory._engine, Base)  # noqa: SLF001

                rec = OutboxRecord(aggregate_id="a3", aggregate_type="X", event_type="E", topic="t", payload=b"{}")

                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    await repo.save(rec)

                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    await repo.mark_dispatched(rec.id)

                # No pending records remain
                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    pending = await repo.get_pending()
                    assert len(pending) == 0

                await factory._engine.dispose()  # noqa: SLF001

            _run(run())

    def test_mark_failed_does_not_appear_in_pending(self) -> None:
        with PostgresContainer("postgres:16-alpine") as container:
            url = _pg_url(container)

            async def run() -> None:
                factory = SqlAlchemySessionFactory(url)
                Base, Model = _make_outbox_model()
                await _create_tables(factory._engine, Base)  # noqa: SLF001

                rec = OutboxRecord(aggregate_id="a4", aggregate_type="X", event_type="E", topic="t", payload=b"{}")

                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    await repo.save(rec)

                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    await repo.mark_failed(rec.id, "network error")

                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    pending = await repo.get_pending()
                    assert len(pending) == 0

                await factory._engine.dispose()  # noqa: SLF001

            _run(run())

    def test_get_pending_respects_limit(self) -> None:
        with PostgresContainer("postgres:16-alpine") as container:
            url = _pg_url(container)

            async def run() -> None:
                factory = SqlAlchemySessionFactory(url)
                Base, Model = _make_outbox_model()
                await _create_tables(factory._engine, Base)  # noqa: SLF001

                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    for i in range(5):
                        await repo.save(OutboxRecord(aggregate_id=f"a{i}", aggregate_type="X", event_type="E", topic="t", payload=b"{}"))

                async with SqlAlchemyUnitOfWork(factory) as uow:
                    repo = SqlAlchemyOutboxRepository(uow.session, Model)
                    pending = await repo.get_pending(limit=3)
                    assert len(pending) == 3

                await factory._engine.dispose()  # noqa: SLF001

            _run(run())
