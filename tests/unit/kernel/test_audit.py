"""Unit tests for §46 — Security Audit Log."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from mp_commons.kernel.security.audit import AuditEvent, AuditStore, InMemoryAuditStore
from mp_commons.kernel.types.ids import EntityId


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(
    principal_id: str = "user-1",
    action: str = "orders:create",
    resource_type: str = "Order",
    resource_id: str = "order-1",
    outcome: str = "allow",
    **kw: Any,
) -> AuditEvent:
    return AuditEvent(
        principal_id=principal_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,  # type: ignore[arg-type]
        **kw,
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# §46.1  AuditEvent
# ---------------------------------------------------------------------------


class TestAuditEvent:
    def test_required_fields(self) -> None:
        ev = _event()
        assert ev.principal_id == "user-1"
        assert ev.action == "orders:create"
        assert ev.resource_type == "Order"
        assert ev.resource_id == "order-1"
        assert ev.outcome == "allow"

    def test_event_id_defaults_to_entity_id(self) -> None:
        ev = _event()
        assert isinstance(ev.event_id, EntityId)
        assert ev.event_id.value  # non-empty

    def test_each_instance_has_unique_event_id(self) -> None:
        a = _event()
        b = _event()
        assert a.event_id != b.event_id

    def test_occurred_at_defaults_to_utc_now(self) -> None:
        before = datetime.now(UTC)
        ev = _event()
        after = datetime.now(UTC)
        assert before <= ev.occurred_at <= after

    def test_metadata_defaults_to_empty_dict(self) -> None:
        ev = _event()
        assert ev.metadata == {}

    def test_explicit_metadata(self) -> None:
        ev = _event(metadata={"ip": "127.0.0.1"})
        assert ev.metadata["ip"] == "127.0.0.1"

    def test_is_frozen(self) -> None:
        import dataclasses

        ev = _event()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            ev.outcome = "deny"  # type: ignore[misc]

    def test_is_allowed_true(self) -> None:
        assert _event(outcome="allow").is_allowed()
        assert not _event(outcome="allow").is_denied()

    def test_is_denied_true(self) -> None:
        assert _event(outcome="deny").is_denied()
        assert not _event(outcome="deny").is_allowed()

    def test_deny_outcome(self) -> None:
        ev = _event(outcome="deny")
        assert ev.outcome == "deny"

    def test_explicit_event_id(self) -> None:
        eid = EntityId("my-id")
        ev = _event(event_id=eid)
        assert ev.event_id == eid


# ---------------------------------------------------------------------------
# §46.2  AuditStore (abstract)
# ---------------------------------------------------------------------------


class TestAuditStoreAbstract:
    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            AuditStore()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# §46.3  InMemoryAuditStore
# ---------------------------------------------------------------------------


class TestInMemoryAuditStore:
    def test_record_and_all(self) -> None:
        store = InMemoryAuditStore()
        ev = _event()
        _run(store.record(ev))
        assert ev in store.all()

    def test_query_returns_all_without_filters(self) -> None:
        store = InMemoryAuditStore()
        for i in range(3):
            _run(store.record(_event(resource_id=f"r-{i}")))
        results = _run(store.query())
        assert len(results) == 3

    def test_query_filter_by_principal_id(self) -> None:
        store = InMemoryAuditStore()
        _run(store.record(_event(principal_id="alice")))
        _run(store.record(_event(principal_id="bob")))
        results = _run(store.query(principal_id="alice"))
        assert len(results) == 1
        assert results[0].principal_id == "alice"

    def test_query_filter_by_from_dt(self) -> None:
        store = InMemoryAuditStore()
        old_ts = datetime(2020, 1, 1, tzinfo=UTC)
        new_ts = datetime(2025, 1, 1, tzinfo=UTC)
        _run(store.record(_event(occurred_at=old_ts)))
        _run(store.record(_event(occurred_at=new_ts)))
        results = _run(store.query(from_dt=datetime(2024, 1, 1, tzinfo=UTC)))
        assert len(results) == 1
        assert results[0].occurred_at == new_ts

    def test_query_filter_by_to_dt(self) -> None:
        store = InMemoryAuditStore()
        old_ts = datetime(2020, 1, 1, tzinfo=UTC)
        new_ts = datetime(2025, 1, 1, tzinfo=UTC)
        _run(store.record(_event(occurred_at=old_ts)))
        _run(store.record(_event(occurred_at=new_ts)))
        results = _run(store.query(to_dt=datetime(2021, 1, 1, tzinfo=UTC)))
        assert len(results) == 1
        assert results[0].occurred_at == old_ts

    def test_query_filter_by_action(self) -> None:
        store = InMemoryAuditStore()
        _run(store.record(_event(action="orders:create")))
        _run(store.record(_event(action="users:delete")))
        results = _run(store.query(action_filter="orders"))
        assert len(results) == 1
        assert "orders" in results[0].action

    def test_query_filter_by_outcome(self) -> None:
        store = InMemoryAuditStore()
        _run(store.record(_event(outcome="allow")))
        _run(store.record(_event(outcome="deny")))
        allows = _run(store.query(outcome="allow"))
        denies = _run(store.query(outcome="deny"))
        assert len(allows) == 1
        assert len(denies) == 1

    def test_query_combined_filters(self) -> None:
        store = InMemoryAuditStore()
        _run(store.record(_event(principal_id="alice", action="orders:create", outcome="allow")))
        _run(store.record(_event(principal_id="alice", action="users:delete", outcome="deny")))
        _run(store.record(_event(principal_id="bob", action="orders:create", outcome="allow")))
        results = _run(store.query(principal_id="alice", outcome="allow"))
        assert len(results) == 1
        assert results[0].action == "orders:create"

    def test_query_limit(self) -> None:
        store = InMemoryAuditStore()
        for i in range(10):
            _run(store.record(_event(resource_id=str(i))))
        results = _run(store.query(limit=3))
        assert len(results) == 3

    def test_query_ordered_oldest_first(self) -> None:
        store = InMemoryAuditStore()
        ts1 = datetime(2024, 1, 1, tzinfo=UTC)
        ts2 = datetime(2024, 6, 1, tzinfo=UTC)
        # Insert out of order
        _run(store.record(_event(occurred_at=ts2)))
        _run(store.record(_event(occurred_at=ts1)))
        results = _run(store.query())
        assert results[0].occurred_at == ts1
        assert results[1].occurred_at == ts2

    def test_empty_store_returns_empty_list(self) -> None:
        store = InMemoryAuditStore()
        assert _run(store.query()) == []

    def test_is_subclass_of_audit_store(self) -> None:
        assert issubclass(InMemoryAuditStore, AuditStore)


# ---------------------------------------------------------------------------
# §46.4  SQLAlchemyAuditStore (with in-memory SQLite via aiosqlite)
# ---------------------------------------------------------------------------


class TestSQLAlchemyAuditStore:
    def _make_store(self) -> tuple[Any, Any]:
        """Return (engine, session_factory) using async in-memory SQLite."""
        import sqlalchemy as sa
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        return engine, factory

    def test_record_and_query_round_trip(self) -> None:
        from mp_commons.adapters.sqlalchemy.audit import SQLAlchemyAuditStore

        engine, factory = self._make_store()

        async def run() -> list[AuditEvent]:
            await SQLAlchemyAuditStore.create_table(engine)
            async with factory() as session:
                store = SQLAlchemyAuditStore(session)
                await store.record(_event())
                await session.commit()
            async with factory() as session:
                store = SQLAlchemyAuditStore(session)
                return await store.query()

        results = asyncio.run(run())
        assert len(results) == 1
        assert results[0].principal_id == "user-1"
        assert results[0].action == "orders:create"
        assert results[0].outcome == "allow"

    def test_query_filter_principal_id(self) -> None:
        from mp_commons.adapters.sqlalchemy.audit import SQLAlchemyAuditStore

        engine, factory = self._make_store()

        async def run() -> list[AuditEvent]:
            await SQLAlchemyAuditStore.create_table(engine)
            async with factory() as session:
                store = SQLAlchemyAuditStore(session)
                await store.record(_event(principal_id="alice"))
                await store.record(_event(principal_id="bob"))
                await session.commit()
            async with factory() as session:
                store = SQLAlchemyAuditStore(session)
                return await store.query(principal_id="alice")

        results = asyncio.run(run())
        assert len(results) == 1
        assert results[0].principal_id == "alice"

    def test_query_filter_outcome(self) -> None:
        from mp_commons.adapters.sqlalchemy.audit import SQLAlchemyAuditStore

        engine, factory = self._make_store()

        async def run() -> tuple[list[AuditEvent], list[AuditEvent]]:
            await SQLAlchemyAuditStore.create_table(engine)
            async with factory() as session:
                store = SQLAlchemyAuditStore(session)
                await store.record(_event(outcome="allow"))
                await store.record(_event(outcome="deny"))
                await session.commit()
            async with factory() as session:
                store = SQLAlchemyAuditStore(session)
                allows = await store.query(outcome="allow")
                denies = await store.query(outcome="deny")
                return allows, denies

        allows, denies = asyncio.run(run())
        assert len(allows) == 1
        assert len(denies) == 1

    def test_query_filter_action(self) -> None:
        from mp_commons.adapters.sqlalchemy.audit import SQLAlchemyAuditStore

        engine, factory = self._make_store()

        async def run() -> list[AuditEvent]:
            await SQLAlchemyAuditStore.create_table(engine)
            async with factory() as session:
                store = SQLAlchemyAuditStore(session)
                await store.record(_event(action="orders:create"))
                await store.record(_event(action="users:delete"))
                await session.commit()
            async with factory() as session:
                store = SQLAlchemyAuditStore(session)
                return await store.query(action_filter="orders")

        results = asyncio.run(run())
        assert len(results) == 1
        assert "orders" in results[0].action

    def test_create_table_idempotent(self) -> None:
        from mp_commons.adapters.sqlalchemy.audit import SQLAlchemyAuditStore

        engine, _ = self._make_store()

        async def run() -> None:
            await SQLAlchemyAuditStore.create_table(engine)
            await SQLAlchemyAuditStore.create_table(engine)  # must not raise

        asyncio.run(run())

    def test_metadata_round_trips_as_json(self) -> None:
        from mp_commons.adapters.sqlalchemy.audit import SQLAlchemyAuditStore

        engine, factory = self._make_store()

        async def run() -> list[AuditEvent]:
            await SQLAlchemyAuditStore.create_table(engine)
            async with factory() as session:
                store = SQLAlchemyAuditStore(session)
                await store.record(_event(metadata={"ip": "1.2.3.4", "corr": "xyz"}))
                await session.commit()
            async with factory() as session:
                store = SQLAlchemyAuditStore(session)
                return await store.query()

        results = asyncio.run(run())
        assert results[0].metadata == {"ip": "1.2.3.4", "corr": "xyz"}


# ---------------------------------------------------------------------------
# §46.5  AuditMiddleware
# ---------------------------------------------------------------------------


class TestAuditMiddleware:
    def _make_store(self) -> InMemoryAuditStore:
        return InMemoryAuditStore()

    def test_records_allow_on_success(self) -> None:
        from mp_commons.application.pipeline.audit_middleware import AuditMiddleware

        store = self._make_store()
        mw = AuditMiddleware(store=store)

        class Cmd:
            pass

        async def run() -> None:
            async def handler(req: Any) -> str:
                return "ok"

            await mw(Cmd(), handler)

        _run(run())
        events = store.all()
        assert len(events) == 1
        assert events[0].outcome == "allow"

    def test_records_deny_and_reraises_on_exception(self) -> None:
        from mp_commons.application.pipeline.audit_middleware import AuditMiddleware

        store = self._make_store()
        mw = AuditMiddleware(store=store)

        class Cmd:
            pass

        async def run() -> None:
            async def failing_handler(req: Any) -> None:
                raise ValueError("boom")

            with pytest.raises(ValueError, match="boom"):
                await mw(Cmd(), failing_handler)

        _run(run())
        events = store.all()
        assert len(events) == 1
        assert events[0].outcome == "deny"

    def test_uses_principal_from_security_context(self) -> None:
        from mp_commons.application.pipeline.audit_middleware import AuditMiddleware
        from mp_commons.kernel.security.principal import Principal
        from mp_commons.kernel.security.security_context import SecurityContext

        store = self._make_store()
        mw = AuditMiddleware(store=store)

        class Cmd:
            pass

        async def run() -> None:
            SecurityContext.set_current(Principal(subject="alice"))
            try:
                await mw(Cmd(), AsyncMock(return_value=None))
            finally:
                SecurityContext.clear()

        _run(run())
        assert store.all()[0].principal_id == "alice"

    def test_anonymous_when_no_principal(self) -> None:
        from mp_commons.application.pipeline.audit_middleware import AuditMiddleware
        from mp_commons.kernel.security.security_context import SecurityContext

        SecurityContext.clear()
        store = self._make_store()
        mw = AuditMiddleware(store=store)

        async def run() -> None:
            await mw(object(), AsyncMock(return_value=None))

        _run(run())
        assert store.all()[0].principal_id == "anonymous"

    def test_resource_id_from_request_id_attr(self) -> None:
        from mp_commons.application.pipeline.audit_middleware import AuditMiddleware

        store = self._make_store()
        mw = AuditMiddleware(store=store)

        class CmdWithId:
            id = "order-99"

        _run(mw(CmdWithId(), AsyncMock(return_value=None)))
        assert store.all()[0].resource_id == "order-99"

    def test_resource_id_defaults_to_dash(self) -> None:
        from mp_commons.application.pipeline.audit_middleware import AuditMiddleware

        store = self._make_store()
        mw = AuditMiddleware(store=store)

        _run(mw(object(), AsyncMock(return_value=None)))
        assert store.all()[0].resource_id == "-"

    def test_custom_action_and_resource_type(self) -> None:
        from mp_commons.application.pipeline.audit_middleware import AuditMiddleware

        store = self._make_store()
        mw = AuditMiddleware(store=store, action="my:action", resource_type="Widget")

        _run(mw(object(), AsyncMock(return_value=None)))
        ev = store.all()[0]
        assert ev.action == "my:action"
        assert ev.resource_type == "Widget"

    def test_action_defaults_to_request_class_name(self) -> None:
        from mp_commons.application.pipeline.audit_middleware import AuditMiddleware

        store = self._make_store()
        mw = AuditMiddleware(store=store)

        class CreateOrder:
            pass

        _run(mw(CreateOrder(), AsyncMock(return_value=None)))
        assert store.all()[0].action == "CreateOrder"

    def test_is_middleware_subclass(self) -> None:
        from mp_commons.application.pipeline.audit_middleware import AuditMiddleware
        from mp_commons.application.pipeline.middleware import Middleware

        assert issubclass(AuditMiddleware, Middleware)


# ---------------------------------------------------------------------------
# Security __init__ exports
# ---------------------------------------------------------------------------


class TestSecurityAuditExports:
    def test_all_audit_names_importable_from_security(self) -> None:
        from mp_commons.kernel.security import AuditEvent, AuditStore, InMemoryAuditStore

        for obj in (AuditEvent, AuditStore, InMemoryAuditStore):
            assert obj is not None

    def test_audit_middleware_importable_from_pipeline(self) -> None:
        from mp_commons.application.pipeline import AuditMiddleware

        assert AuditMiddleware is not None

    def test_sqlalchemy_audit_store_importable_from_adapters(self) -> None:
        from mp_commons.adapters.sqlalchemy import SQLAlchemyAuditStore

        assert SQLAlchemyAuditStore is not None
