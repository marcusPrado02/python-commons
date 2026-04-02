"""Unit tests for §27 – SQLAlchemy adapter (UoW, Repository, Outbox, EventStore, Mixins).

Uses an in-memory SQLite database via *aiosqlite* — no running server needed.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
from typing import Any
import uuid

import pytest
from sqlalchemy import DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from mp_commons.adapters.sqlalchemy.event_store import SQLAlchemyEventStore
from mp_commons.adapters.sqlalchemy.mixins import SoftDeleteMixin, TimestampMixin
from mp_commons.adapters.sqlalchemy.outbox import SqlAlchemyOutboxRepository
from mp_commons.adapters.sqlalchemy.repository import SqlAlchemyRepositoryBase
from mp_commons.adapters.sqlalchemy.session import SqlAlchemySessionFactory
from mp_commons.adapters.sqlalchemy.uow import SqlAlchemyUnitOfWork
from mp_commons.application.event_sourcing.store import OptimisticConcurrencyError
from mp_commons.application.event_sourcing.stored_event import StoredEvent
from mp_commons.kernel.errors import NotFoundError
from mp_commons.kernel.messaging.outbox import OutboxRecord, OutboxStatus

# ---------------------------------------------------------------------------
# Shared ORM base and test models
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class ItemModel(Base):
    """Minimal model for repository + UoW tests."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))


class ItemWithTimestamps(TimestampMixin, Base):
    """Model that uses TimestampMixin."""

    __tablename__ = "items_ts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))


class ItemSoftDelete(SoftDeleteMixin, Base):
    """Model that uses SoftDeleteMixin."""

    __tablename__ = "items_sd"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))


class OutboxRecordModel(Base):
    """Concrete ORM model for outbox records."""

    __tablename__ = "outbox_records"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    aggregate_id: Mapped[str] = mapped_column(String(256))
    aggregate_type: Mapped[str] = mapped_column(String(256))
    event_type: Mapped[str] = mapped_column(String(256))
    topic: Mapped[str] = mapped_column(String(256))
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    headers: Mapped[Any] = mapped_column(SQLiteJSON, default=dict)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)


class IdempotencyModel(Base):
    """Concrete ORM model for idempotency store."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    response: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(32), default="PROCESSING")


# ---------------------------------------------------------------------------
# Engine + session fixtures
# ---------------------------------------------------------------------------


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)


def _make_session_factory(engine) -> async_sessionmaker:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _setup_engine():
    engine = _make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await SQLAlchemyEventStore.create_table(engine)
    return engine


# ---------------------------------------------------------------------------
# Fake EntityId for repository tests
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class FakeId:
    value: int


# ---------------------------------------------------------------------------
# SqlAlchemySessionFactory
# ---------------------------------------------------------------------------


class TestSessionFactory:
    def test_returns_callable_session(self) -> None:
        factory = SqlAlchemySessionFactory("sqlite+aiosqlite:///:memory:")

        async def run():
            session = factory()
            assert session is not None
            await session.close()
            await factory.dispose()

        asyncio.run(run())


# ---------------------------------------------------------------------------
# SqlAlchemyUnitOfWork
# ---------------------------------------------------------------------------


class TestUnitOfWork:
    def test_commit_persists_data(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with SqlAlchemyUnitOfWork(sf) as uow:
                uow.session.add(ItemModel(id=1, name="alpha"))

            # read back in a fresh session
            async with sf() as s:
                item = await s.get(ItemModel, 1)
            assert item is not None
            assert item.name == "alpha"
            await engine.dispose()

        asyncio.run(run())

    def test_exception_triggers_rollback(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            with pytest.raises(ValueError):
                async with SqlAlchemyUnitOfWork(sf) as uow:
                    uow.session.add(ItemModel(id=2, name="beta"))
                    raise ValueError("oops")

            async with sf() as s:
                item = await s.get(ItemModel, 2)
            assert item is None
            await engine.dispose()

        asyncio.run(run())

    def test_commit_then_rollback_independent_contexts(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with SqlAlchemyUnitOfWork(sf) as uow:
                uow.session.add(ItemModel(id=3, name="committed"))

            with pytest.raises(RuntimeError):
                async with SqlAlchemyUnitOfWork(sf) as uow2:
                    uow2.session.add(ItemModel(id=4, name="rolled-back"))
                    raise RuntimeError("fail")

            async with sf() as s:
                assert await s.get(ItemModel, 3) is not None
                assert await s.get(ItemModel, 4) is None
            await engine.dispose()

        asyncio.run(run())


# ---------------------------------------------------------------------------
# SqlAlchemyRepositoryBase
# ---------------------------------------------------------------------------


class TestRepositoryBase:
    def test_save_and_get(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with sf() as s:
                repo = SqlAlchemyRepositoryBase(s, ItemModel)
                item = ItemModel(id=10, name="repo-item")
                await repo.save(item)
                await s.commit()

            async with sf() as s:
                repo = SqlAlchemyRepositoryBase(s, ItemModel)
                result = await repo.get(FakeId(10))
                assert result is not None
                assert result.name == "repo-item"
            await engine.dispose()

        asyncio.run(run())

    def test_get_nonexistent_returns_none(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with sf() as s:
                repo = SqlAlchemyRepositoryBase(s, ItemModel)
                assert await repo.get(FakeId(999)) is None
            await engine.dispose()

        asyncio.run(run())

    def test_get_or_raise_missing(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with sf() as s:
                repo = SqlAlchemyRepositoryBase(s, ItemModel)
                with pytest.raises(NotFoundError):
                    await repo.get_or_raise(FakeId(999))
            await engine.dispose()

        asyncio.run(run())

    def test_delete_removes_item(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with sf() as s:
                s.add(ItemModel(id=20, name="to-delete"))
                await s.commit()

            async with sf() as s:
                repo = SqlAlchemyRepositoryBase(s, ItemModel)
                await repo.delete(FakeId(20))
                await s.commit()

            async with sf() as s:
                repo = SqlAlchemyRepositoryBase(s, ItemModel)
                assert await repo.get(FakeId(20)) is None
            await engine.dispose()

        asyncio.run(run())


# ---------------------------------------------------------------------------
# SqlAlchemyOutboxRepository
# ---------------------------------------------------------------------------


class TestOutboxRepository:
    def _make_record(self, status: OutboxStatus = OutboxStatus.PENDING) -> OutboxRecord:
        return OutboxRecord(
            id=str(uuid.uuid4()),
            aggregate_id="agg-1",
            aggregate_type="Order",
            event_type="OrderCreated",
            topic="orders",
            payload=b'{"id":1}',
            headers={"x-tenant": "t1"},
            status=status,
            created_at=datetime.datetime.now(datetime.UTC),
        )

    def test_save_and_get_pending(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            record = self._make_record()
            async with sf() as s:
                repo = SqlAlchemyOutboxRepository(s, OutboxRecordModel)
                await repo.save(record)
                await s.commit()

            async with sf() as s:
                repo = SqlAlchemyOutboxRepository(s, OutboxRecordModel)
                pending = await repo.get_pending(limit=10)
            assert len(pending) == 1
            assert pending[0].id == record.id
            await engine.dispose()

        asyncio.run(run())

    def test_mark_dispatched(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            record = self._make_record()
            async with sf() as s:
                repo = SqlAlchemyOutboxRepository(s, OutboxRecordModel)
                await repo.save(record)
                await s.commit()

            async with sf() as s:
                repo = SqlAlchemyOutboxRepository(s, OutboxRecordModel)
                await repo.mark_dispatched(record.id)
                await s.commit()

            async with sf() as s:
                repo = SqlAlchemyOutboxRepository(s, OutboxRecordModel)
                pending = await repo.get_pending()
            assert pending == []
            await engine.dispose()

        asyncio.run(run())

    def test_mark_failed(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            record = self._make_record()
            async with sf() as s:
                repo = SqlAlchemyOutboxRepository(s, OutboxRecordModel)
                await repo.save(record)
                await s.commit()

            async with sf() as s:
                repo = SqlAlchemyOutboxRepository(s, OutboxRecordModel)
                await repo.mark_failed(record.id, "connection refused")
                await s.commit()

            async with sf() as s:
                from sqlalchemy import select

                result = await s.execute(
                    select(OutboxRecordModel).where(OutboxRecordModel.id == record.id)
                )
                row = result.scalar_one()
            assert row.status == OutboxStatus.FAILED.value
            assert row.last_error == "connection refused"
            await engine.dispose()

        asyncio.run(run())

    def test_dispatched_not_in_pending(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            r1, r2 = self._make_record(), self._make_record()
            async with sf() as s:
                repo = SqlAlchemyOutboxRepository(s, OutboxRecordModel)
                await repo.save(r1)
                await repo.save(r2)
                await s.commit()

            async with sf() as s:
                repo = SqlAlchemyOutboxRepository(s, OutboxRecordModel)
                await repo.mark_dispatched(r1.id)
                await s.commit()

            async with sf() as s:
                repo = SqlAlchemyOutboxRepository(s, OutboxRecordModel)
                pending = await repo.get_pending()
            assert len(pending) == 1
            assert pending[0].id == r2.id
            await engine.dispose()

        asyncio.run(run())


# ---------------------------------------------------------------------------
# SQLAlchemyEventStore
# ---------------------------------------------------------------------------


def _make_event(stream_id: str, version: int, payload: bytes = b"{}") -> StoredEvent:
    return StoredEvent(
        stream_id=stream_id,
        version=version,
        event_type="SomethingHappened",
        payload=payload,
        metadata={"correlation_id": "abc"},
        occurred_at=datetime.datetime.now(datetime.UTC),
    )


class TestSQLAlchemyEventStore:
    def test_append_and_load(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            events = [_make_event("Order-1", 1), _make_event("Order-1", 2)]
            async with sf() as s:
                store = SQLAlchemyEventStore(s)
                await store.append("Order-1", events, expected_version=0)
                await s.commit()

            async with sf() as s:
                store = SQLAlchemyEventStore(s)
                loaded = await store.load("Order-1")
            assert len(loaded) == 2
            assert loaded[0].version == 1
            assert loaded[1].version == 2
            assert loaded[0].metadata == {"correlation_id": "abc"}
            await engine.dispose()

        asyncio.run(run())

    def test_optimistic_concurrency_error(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with sf() as s:
                store = SQLAlchemyEventStore(s)
                await store.append("Order-2", [_make_event("Order-2", 1)], expected_version=0)
                await s.commit()

            async with sf() as s:
                store = SQLAlchemyEventStore(s)
                with pytest.raises(OptimisticConcurrencyError) as exc_info:
                    # wrong expected_version (should be 1, not 0)
                    await store.append("Order-2", [_make_event("Order-2", 2)], expected_version=0)
            assert exc_info.value.expected == 0
            assert exc_info.value.actual == 1
            await engine.dispose()

        asyncio.run(run())

    def test_load_from_version_filters(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            events = [_make_event("S-1", i) for i in range(1, 6)]
            async with sf() as s:
                store = SQLAlchemyEventStore(s)
                await store.append("S-1", events, expected_version=0)
                await s.commit()

            async with sf() as s:
                store = SQLAlchemyEventStore(s)
                loaded = await store.load("S-1", from_version=3)
            assert [e.version for e in loaded] == [4, 5]
            await engine.dispose()

        asyncio.run(run())

    def test_load_empty_stream(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with sf() as s:
                store = SQLAlchemyEventStore(s)
                loaded = await store.load("no-such-stream")
            assert loaded == []
            await engine.dispose()

        asyncio.run(run())

    def test_append_to_new_stream_wrong_version(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with sf() as s:
                store = SQLAlchemyEventStore(s)
                with pytest.raises(OptimisticConcurrencyError):
                    await store.append("S-new", [_make_event("S-new", 1)], expected_version=1)
            await engine.dispose()

        asyncio.run(run())

    def test_payload_roundtrip(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            raw = b"\x00\x01\x02\xffbinary"
            async with sf() as s:
                store = SQLAlchemyEventStore(s)
                await store.append("S-bin", [_make_event("S-bin", 1, raw)], expected_version=0)
                await s.commit()

            async with sf() as s:
                store = SQLAlchemyEventStore(s)
                loaded = await store.load("S-bin")
            assert loaded[0].payload == raw
            await engine.dispose()

        asyncio.run(run())


# ---------------------------------------------------------------------------
# TimestampMixin (§27.8)
# ---------------------------------------------------------------------------


class TestTimestampMixin:
    def test_columns_present_in_table(self) -> None:
        cols = {c.name for c in ItemWithTimestamps.__table__.columns}
        assert "created_at" in cols
        assert "updated_at" in cols

    def test_created_at_not_null_after_insert(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with sf() as s:
                item = ItemWithTimestamps(id=1, name="ts-test")
                s.add(item)
                await s.commit()
                await s.refresh(item)
            # server_default was applied — created_at is not None
            # (SQLite returns a string; just check it's truthy)
            assert item.created_at is not None
            await engine.dispose()

        asyncio.run(run())

    def test_mixin_adds_both_columns(self) -> None:
        assert hasattr(ItemWithTimestamps, "created_at")
        assert hasattr(ItemWithTimestamps, "updated_at")


# ---------------------------------------------------------------------------
# SoftDeleteMixin (§27.9)
# ---------------------------------------------------------------------------


class TestSoftDeleteMixin:
    def test_deleted_at_column_present(self) -> None:
        cols = {c.name for c in ItemSoftDelete.__table__.columns}
        assert "deleted_at" in cols

    def test_is_deleted_false_by_default(self) -> None:
        item = ItemSoftDelete(id=1, name="live")
        assert item.is_deleted is False

    def test_soft_delete_sets_deleted_at(self) -> None:
        item = ItemSoftDelete(id=2, name="doomed")
        item.soft_delete()
        assert item.is_deleted is True
        assert isinstance(item.deleted_at, datetime.datetime)

    def test_not_deleted_filter_excludes_soft_deleted(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with sf() as s:
                live = ItemSoftDelete(id=10, name="live")
                deleted = ItemSoftDelete(id=11, name="gone")
                deleted.soft_delete()
                s.add(live)
                s.add(deleted)
                await s.commit()

            async with sf() as s:
                from sqlalchemy import select

                stmt = select(ItemSoftDelete).where(ItemSoftDelete.not_deleted_filter())
                result = await s.execute(stmt)
                rows = result.scalars().all()
            names = [r.name for r in rows]
            assert "live" in names
            assert "gone" not in names
            await engine.dispose()

        asyncio.run(run())

    def test_soft_delete_persists_in_db(self) -> None:
        async def run() -> None:
            engine = await _setup_engine()
            sf = _make_session_factory(engine)

            async with sf() as s:
                item = ItemSoftDelete(id=20, name="persist-test")
                s.add(item)
                await s.commit()

            async with sf() as s:
                item = await s.get(ItemSoftDelete, 20)
                item.soft_delete()
                await s.commit()

            async with sf() as s:
                item = await s.get(ItemSoftDelete, 20)
            assert item.is_deleted is True
            await engine.dispose()

        asyncio.run(run())


# ===========================================================================
# §58.4 – SQLAlchemySpecification
# ===========================================================================


class TestSQLAlchemySpecification:
    """§58.4 – SQLAlchemySpecification produces ColumnElements and composes."""

    def _make_spec_and_model(self):
        from sqlalchemy import Boolean
        from sqlalchemy.orm import DeclarativeBase, mapped_column

        from mp_commons.adapters.sqlalchemy.specification import SQLAlchemySpecification

        class Spec58Base(DeclarativeBase):
            pass

        class ProductModel(Spec58Base):
            __tablename__ = "products_test"
            id: Mapped[int] = mapped_column(Integer, primary_key=True)
            active: Mapped[bool] = mapped_column(Boolean, default=True)
            price: Mapped[int] = mapped_column(Integer, default=0)

        class ActiveSpec(SQLAlchemySpecification):
            def is_satisfied_by(self, candidate) -> bool:
                return candidate.active

            def to_expression(self):
                from sqlalchemy import true

                return ProductModel.active.is_(true())

        class PricedSpec(SQLAlchemySpecification):
            def __init__(self, threshold: int) -> None:
                self._threshold = threshold

            def is_satisfied_by(self, candidate) -> bool:
                return candidate.price >= self._threshold

            def to_expression(self):
                return ProductModel.price >= self._threshold

        return ProductModel, ActiveSpec, PricedSpec

    def test_to_expression_returns_column_element(self):
        from sqlalchemy.sql.elements import ClauseElement

        _, ActiveSpec, _ = self._make_spec_and_model()
        expr = ActiveSpec().to_expression()
        assert isinstance(expr, ClauseElement)

    def test_and_spec_produces_and_expression(self):
        from sqlalchemy.sql.elements import ClauseElement

        _, ActiveSpec, PricedSpec = self._make_spec_and_model()
        spec = ActiveSpec() & PricedSpec(100)
        expr = spec.to_expression()
        assert isinstance(expr, ClauseElement)
        assert "AND" in str(expr).upper()

    def test_or_spec_produces_or_expression(self):
        from sqlalchemy.sql.elements import ClauseElement

        _, ActiveSpec, PricedSpec = self._make_spec_and_model()
        spec = ActiveSpec() | PricedSpec(100)
        expr = spec.to_expression()
        assert isinstance(expr, ClauseElement)
        assert "OR" in str(expr).upper()

    def test_not_spec_produces_not_expression(self):
        from sqlalchemy.sql.elements import ClauseElement

        _, ActiveSpec, _ = self._make_spec_and_model()
        spec = ~ActiveSpec()
        expr = spec.to_expression()
        assert isinstance(expr, ClauseElement)
        assert "NOT" in str(expr).upper()

    def test_in_memory_is_satisfied_by_still_works(self):
        _, ActiveSpec, PricedSpec = self._make_spec_and_model()

        class FakeProduct:
            def __init__(self, active: bool, price: int) -> None:
                self.active = active
                self.price = price

        spec = ActiveSpec() & PricedSpec(50)
        assert spec.is_satisfied_by(FakeProduct(True, 100)) is True
        assert spec.is_satisfied_by(FakeProduct(False, 100)) is False

    def test_chained_and_spec(self):
        from sqlalchemy.sql.elements import ClauseElement

        _, ActiveSpec, PricedSpec = self._make_spec_and_model()
        spec = ActiveSpec() & PricedSpec(10) & PricedSpec(50)
        expr = spec.to_expression()
        assert isinstance(expr, ClauseElement)

    def test_non_sql_spec_raises_type_error_on_and(self):
        from mp_commons.adapters.sqlalchemy.specification import (
            SQLAlchemyAndSpecification,
            SQLAlchemySpecification,
        )
        from mp_commons.kernel.ddd.specification import BaseSpecification

        class NonSqlSpec(BaseSpecification):
            def is_satisfied_by(self, candidate) -> bool:
                return True

        class SqlSpec(SQLAlchemySpecification):
            def is_satisfied_by(self, candidate) -> bool:
                return True

            def to_expression(self):
                from sqlalchemy import true

                return true()

        with pytest.raises(TypeError, match="to_expression"):
            composite = SQLAlchemyAndSpecification(SqlSpec(), NonSqlSpec())
            composite.to_expression()


# ===========================================================================
# §61.5 – TenantFilter SQLAlchemy event
# ===========================================================================


class TestTenantFilter:
    """§61.5 – TenantFilter install/uninstall lifecycle."""

    def test_is_not_installed_by_default(self):
        from mp_commons.adapters.sqlalchemy.tenant_filter import TenantFilter

        TenantFilter.uninstall()  # ensure clean state
        assert TenantFilter.is_installed() is False

    def test_install_sets_installed_flag(self):
        from mp_commons.adapters.sqlalchemy.tenant_filter import TenantFilter

        try:
            TenantFilter.install()
            assert TenantFilter.is_installed() is True
        finally:
            TenantFilter.uninstall()

    def test_install_is_idempotent(self):
        from mp_commons.adapters.sqlalchemy.tenant_filter import TenantFilter

        try:
            TenantFilter.install()
            TenantFilter.install()  # second call is no-op
            assert TenantFilter.is_installed() is True
        finally:
            TenantFilter.uninstall()

    def test_uninstall_removes_flag(self):
        from mp_commons.adapters.sqlalchemy.tenant_filter import TenantFilter

        TenantFilter.install()
        TenantFilter.uninstall()
        assert TenantFilter.is_installed() is False

    def test_uninstall_is_safe_when_not_installed(self):
        from mp_commons.adapters.sqlalchemy.tenant_filter import TenantFilter

        TenantFilter.uninstall()
        TenantFilter.uninstall()  # safe no-op
        assert TenantFilter.is_installed() is False
