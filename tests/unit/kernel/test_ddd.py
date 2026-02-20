"""Unit tests for DDD building blocks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from mp_commons.kernel.ddd import (
    AggregateRoot,
    AndSpecification,
    BaseSpecification,
    DomainEvent,
    DomainEventBus,
    Entity,
    Invariant,
    NotSpecification,
    OrSpecification,
    OutboxPublisher,
    Saga,
    Specification,
    TenantContext,
    UnitOfWork,
    ValueObject,
    ensure,
)
from mp_commons.kernel.errors import InvariantViolationError, ValidationError
from mp_commons.kernel.types import EntityId, TenantId


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Name(ValueObject):
    first: str
    last: str

    def full(self) -> str:
        return f"{self.first} {self.last}"


class User(Entity):
    def __init__(self, id: EntityId, name: str, active: bool = True) -> None:
        super().__init__(id)
        self.name = name
        self.active = active


@dataclass(frozen=True)
class UserCreated(DomainEvent):
    user_id: str = ""


class UserAggregate(AggregateRoot):
    def __init__(self, id: EntityId, name: str) -> None:
        super().__init__(id)
        self.name = name

    def rename(self, new_name: str) -> None:
        Invariant.require(bool(new_name), "Name cannot be empty")
        self.name = new_name
        self._raise_event(UserCreated(user_id=str(self.id)))


# ---------------------------------------------------------------------------
# ValueObject
# ---------------------------------------------------------------------------


class TestValueObject:
    def test_equality_by_fields(self) -> None:
        a = Name("Alice", "Smith")
        b = Name("Alice", "Smith")
        c = Name("Bob", "Smith")
        assert a == b
        assert a != c

    def test_frozen(self) -> None:
        n = Name("Alice", "Smith")
        with pytest.raises((AttributeError, TypeError)):
            n.first = "Bob"  # type: ignore[misc]

    def test_hashable(self) -> None:
        names = {Name("Alice", "Smith"), Name("Alice", "Smith")}
        assert len(names) == 1


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


class TestEntity:
    def test_id_based_equality(self) -> None:
        uid = EntityId("user-1")
        a = User(id=uid, name="Alice")
        b = User(id=uid, name="Bob")  # same id, different name
        assert a == b

    def test_different_id_not_equal(self) -> None:
        a = User(id=EntityId("1"), name="Alice")
        b = User(id=EntityId("2"), name="Alice")
        assert a != b

    def test_hashable(self) -> None:
        uid = EntityId("u1")
        users = {User(id=uid, name="A"), User(id=uid, name="B")}
        assert len(users) == 1


# ---------------------------------------------------------------------------
# DomainEvent
# ---------------------------------------------------------------------------


class TestDomainEvent:
    def test_event_has_id_and_timestamp(self) -> None:
        evt = UserCreated(user_id="u1")
        assert evt.event_id
        assert isinstance(evt.occurred_at, datetime)
        assert evt.occurred_at.tzinfo == timezone.utc

    def test_frozen(self) -> None:
        evt = UserCreated(user_id="u1")
        with pytest.raises((AttributeError, TypeError)):
            evt.user_id = "u2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AggregateRoot
# ---------------------------------------------------------------------------


class TestAggregateRoot:
    def test_collect_events(self) -> None:
        agg = UserAggregate(id=EntityId("a1"), name="Alice")
        agg.rename("Alicia")
        events = agg.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserCreated)

    def test_collect_clears_queue(self) -> None:
        agg = UserAggregate(id=EntityId("a2"), name="Alice")
        agg.rename("Alicia")
        agg.collect_events()
        assert agg.collect_events() == []

    def test_pull_events_canonical_name(self) -> None:
        agg = UserAggregate(id=EntityId("a4"), name="Alice")
        agg.rename("Alicia")
        events = agg.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], UserCreated)

    def test_pull_events_clears_list(self) -> None:
        agg = UserAggregate(id=EntityId("a5"), name="Alice")
        agg.rename("Alicia")
        agg.pull_events()
        assert agg.pull_events() == []

    def test_version_increments(self) -> None:
        agg = UserAggregate(id=EntityId("a3"), name="Alice")
        v0 = agg.version
        agg.rename("Alicia")
        assert agg.version == v0 + 1


# ---------------------------------------------------------------------------
# Invariant
# ---------------------------------------------------------------------------


class TestInvariant:
    def test_require_passes_truthy(self) -> None:
        Invariant.require(True, "should not raise")

    def test_require_raises_falsy(self) -> None:
        with pytest.raises(InvariantViolationError, match="name"):
            Invariant.require(False, "name is required")

    def test_ensure_passes(self) -> None:
        Invariant.ensure(1 + 1 == 2, "math")

    def test_ensure_raises(self) -> None:
        with pytest.raises(InvariantViolationError):
            Invariant.ensure(False, "impossible")


# ---------------------------------------------------------------------------
# Specification
# ---------------------------------------------------------------------------


@dataclass
class IsActive(BaseSpecification[User]):
    def is_satisfied_by(self, candidate: User) -> bool:
        return candidate.active


@dataclass
class NameStartsWith(BaseSpecification[User]):
    prefix: str

    def is_satisfied_by(self, candidate: User) -> bool:
        return candidate.name.startswith(self.prefix)


class TestSpecification:
    def test_simple_spec(self) -> None:
        spec = IsActive()
        assert spec.is_satisfied_by(User(id=EntityId("1"), name="A", active=True))
        assert not spec.is_satisfied_by(User(id=EntityId("2"), name="B", active=False))

    def test_and_spec(self) -> None:
        spec = IsActive().and_(NameStartsWith("Al"))
        assert spec.is_satisfied_by(User(id=EntityId("1"), name="Alice", active=True))
        assert not spec.is_satisfied_by(User(id=EntityId("2"), name="Alice", active=False))

    def test_or_spec(self) -> None:
        spec = IsActive().or_(NameStartsWith("Z"))
        assert spec.is_satisfied_by(User(id=EntityId("1"), name="Zara", active=False))

    def test_not_spec(self) -> None:
        spec = IsActive().not_()
        assert spec.is_satisfied_by(User(id=EntityId("1"), name="A", active=False))

    # --- operator overloads ---

    def test_and_operator(self) -> None:
        spec = IsActive() & NameStartsWith("Al")
        assert spec.is_satisfied_by(User(id=EntityId("1"), name="Alice", active=True))
        assert not spec.is_satisfied_by(User(id=EntityId("2"), name="Alice", active=False))

    def test_or_operator(self) -> None:
        spec = IsActive() | NameStartsWith("Z")
        assert spec.is_satisfied_by(User(id=EntityId("1"), name="Zara", active=False))
        assert spec.is_satisfied_by(User(id=EntityId("2"), name="Bob", active=True))
        assert not spec.is_satisfied_by(User(id=EntityId("3"), name="Bob", active=False))

    def test_invert_operator(self) -> None:
        spec = ~IsActive()
        assert spec.is_satisfied_by(User(id=EntityId("1"), name="A", active=False))
        assert not spec.is_satisfied_by(User(id=EntityId("2"), name="B", active=True))

    def test_operators_produce_correct_types(self) -> None:
        assert isinstance(IsActive() & NameStartsWith("A"), AndSpecification)
        assert isinstance(IsActive() | NameStartsWith("A"), OrSpecification)
        assert isinstance(~IsActive(), NotSpecification)

    def test_specification_alias_is_base(self) -> None:
        assert Specification is BaseSpecification


# ---------------------------------------------------------------------------
# TenantContext
# ---------------------------------------------------------------------------


class TestTenantContext:
    def test_set_and_get(self) -> None:
        tid = TenantId("tenant-1")
        token = TenantContext.set(tid)
        try:
            assert TenantContext.get() == tid
        finally:
            TenantContext.reset(token)

    def test_get_returns_none_when_unset(self) -> None:
        # Ensure clean state
        TenantContext.clear()
        assert TenantContext.get() is None

    def test_require_returns_tenant_when_set(self) -> None:
        tid = TenantId("t-req")
        token = TenantContext.set(tid)
        try:
            assert TenantContext.require() == tid
        finally:
            TenantContext.reset(token)

    def test_require_raises_when_not_set(self) -> None:
        TenantContext.clear()
        with pytest.raises(ValidationError):
            TenantContext.require()

    def test_isolated_per_task(self) -> None:
        results: list[TenantId | None] = []

        async def worker(tid: TenantId) -> None:
            token = TenantContext.set(tid)
            await asyncio.sleep(0)
            results.append(TenantContext.get())
            TenantContext.reset(token)

        async def run() -> None:
            await asyncio.gather(
                worker(TenantId("t1")),
                worker(TenantId("t2")),
            )

        asyncio.run(run())
        assert set(results) == {TenantId("t1"), TenantId("t2")}


# ---------------------------------------------------------------------------
# UnitOfWork (4.10)
# ---------------------------------------------------------------------------


class TestUnitOfWork:
    def test_commits_on_clean_exit(self) -> None:
        log: list[str] = []

        class FakeUoW(UnitOfWork):
            async def commit(self) -> None:
                log.append("commit")

            async def rollback(self) -> None:
                log.append("rollback")

        async def _run() -> None:
            async with FakeUoW():
                pass

        asyncio.run(_run())
        assert log == ["commit"]

    def test_rolls_back_on_exception(self) -> None:
        log: list[str] = []

        class FakeUoW(UnitOfWork):
            async def commit(self) -> None:
                log.append("commit")

            async def rollback(self) -> None:
                log.append("rollback")

        async def _run() -> None:
            async with FakeUoW():
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            asyncio.run(_run())

        assert log == ["rollback"]


# ---------------------------------------------------------------------------
# ensure() shorthand (4.5)
# ---------------------------------------------------------------------------


class TestEnsure:
    def test_passes_truthy(self) -> None:
        ensure(True, "ok")

    def test_raises_falsy(self) -> None:
        with pytest.raises(InvariantViolationError, match="fail"):
            ensure(False, "fail")


# ---------------------------------------------------------------------------
# Saga (4.15)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PaymentReceived(DomainEvent):
    amount: int


@dataclass(frozen=True)
class GoodsShipped(DomainEvent):
    tracking: str


class TestSaga:
    def test_handle_routes_to_correct_handler(self) -> None:
        log: list[str] = []

        class OrderSaga(Saga):
            def __init__(self, saga_id: EntityId) -> None:
                super().__init__(saga_id)
                self._register(PaymentReceived, self._on_payment)
                self._register(GoodsShipped, self._on_shipped)

            async def _on_payment(self, event: PaymentReceived) -> None:
                log.append(f"payment:{event.amount}")

            async def _on_shipped(self, event: GoodsShipped) -> None:
                log.append(f"shipped:{event.tracking}")
                self._mark_completed()

        async def _run() -> None:
            saga = OrderSaga(EntityId.generate())
            assert not saga.completed
            await saga.handle(PaymentReceived(amount=100))
            assert log == ["payment:100"]
            assert not saga.completed
            await saga.handle(GoodsShipped(tracking="TRK-1"))
            assert log == ["payment:100", "shipped:TRK-1"]
            assert saga.completed

        asyncio.run(_run())

    def test_unregistered_event_silently_ignored(self) -> None:
        class EmptySaga(Saga):
            pass

        async def _run() -> None:
            saga = EmptySaga(EntityId.generate())
            await saga.handle(PaymentReceived(amount=50))
            assert not saga.completed

        asyncio.run(_run())

    def test_saga_id_accessible(self) -> None:
        class EmptySaga(Saga):
            pass

        eid = EntityId.generate()
        assert EmptySaga(eid).saga_id == eid


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.kernel.ddd")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing from mp_commons.kernel.ddd"

    def test_outbox_publisher_importable(self) -> None:
        assert OutboxPublisher is not None

    def test_event_bus_importable(self) -> None:
        assert DomainEventBus is not None
