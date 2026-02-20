"""Unit tests for DDD building blocks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from mp_commons.kernel.ddd import (
    AggregateRoot,
    DomainEvent,
    Entity,
    Invariant,
    Specification,
    TenantContext,
    ValueObject,
)
from mp_commons.kernel.errors import InvariantViolationError
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


@dataclass
class User(Entity):
    name: str
    active: bool = True


@dataclass(frozen=True)
class UserCreated(DomainEvent):
    user_id: str
    event_type: str = "user.created"


@dataclass
class UserAggregate(AggregateRoot):
    name: str
    _events: list = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._events is None:
            self._events = []

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
class IsActive(Specification[User]):
    def is_satisfied_by(self, candidate: User) -> bool:
        return candidate.active


@dataclass
class NameStartsWith(Specification[User]):
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
        assert TenantContext.get() is None

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
