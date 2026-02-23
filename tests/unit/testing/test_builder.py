"""Unit tests for Builder[T] generic base (§38.5)."""
from __future__ import annotations

import copy
import dataclasses
from typing import Any

import pytest

from mp_commons.testing.generators.builder import Builder, DataclassBuilder


# ---------------------------------------------------------------------------
# Test domain objects
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Point:
    x: float
    y: float


@dataclasses.dataclass
class Order:
    order_id: str
    amount: int
    status: str = "pending"


# ---------------------------------------------------------------------------
# Concrete subclass helpers
# ---------------------------------------------------------------------------


class PointBuilder(DataclassBuilder[Point]):
    _cls = Point

    def __init__(self) -> None:
        super().__init__()
        self._attrs = {"x": 0.0, "y": 0.0}


class OrderBuilder(Builder[Order]):
    def __init__(self) -> None:
        super().__init__()
        self._attrs = {
            "order_id": "ord-1",
            "amount": 100,
            "status": "pending",
        }

    def build(self) -> Order:
        return Order(**self._attrs)


# ---------------------------------------------------------------------------
# §38.5 — Builder[T]
# ---------------------------------------------------------------------------


class TestBuilderBase:
    def test_with_returns_new_instance(self) -> None:
        b1 = OrderBuilder()
        b2 = b1.with_(status="paid")
        assert b1 is not b2

    def test_with_does_not_mutate_original(self) -> None:
        b1 = OrderBuilder()
        b1.with_(status="paid")
        assert b1.get("status") == "pending"

    def test_with_chaining(self) -> None:
        b = OrderBuilder().with_(order_id="ord-99").with_(amount=999)
        o = b.build()
        assert o.order_id == "ord-99"
        assert o.amount == 999

    def test_with_multiple_keys_at_once(self) -> None:
        o = OrderBuilder().with_(order_id="x", amount=5, status="cancelled").build()
        assert o.order_id == "x"
        assert o.amount == 5
        assert o.status == "cancelled"

    def test_original_unchanged_after_chaining(self) -> None:
        base = OrderBuilder()
        paid = base.with_(status="paid")
        failed = base.with_(status="failed")
        assert base.build().status == "pending"
        assert paid.build().status == "paid"
        assert failed.build().status == "failed"

    def test_override_single_key(self) -> None:
        b = OrderBuilder().override("amount", 42)
        assert b.build().amount == 42

    def test_override_returns_new_instance(self) -> None:
        b1 = OrderBuilder()
        b2 = b1.override("amount", 1)
        assert b1 is not b2

    def test_attrs_snapshot(self) -> None:
        b = OrderBuilder()
        snap = b.attrs
        assert snap["status"] == "pending"
        snap["status"] = "mutated"
        # Snapshot is a copy — original builder not affected
        assert b.get("status") == "pending"

    def test_get_existing_key(self) -> None:
        b = OrderBuilder()
        assert b.get("amount") == 100

    def test_get_missing_key_returns_default(self) -> None:
        b = OrderBuilder()
        assert b.get("nonexistent") is None
        assert b.get("nonexistent", "fallback") == "fallback"

    def test_call_builds_object(self) -> None:
        b = OrderBuilder()
        o = b()
        assert isinstance(o, Order)
        assert o.order_id == "ord-1"

    def test_call_with_overrides(self) -> None:
        b = OrderBuilder()
        o = b(status="paid", amount=9999)
        assert o.status == "paid"
        assert o.amount == 9999
        # Base builder unchanged
        assert b.get("status") == "pending"

    def test_build_not_implemented_on_base(self) -> None:
        class Bare(Builder[Any]):
            pass

        with pytest.raises(NotImplementedError):
            Bare().build()

    def test_multiple_builders_are_independent(self) -> None:
        b1 = OrderBuilder().with_(amount=10)
        b2 = OrderBuilder().with_(amount=20)
        assert b1.build().amount == 10
        assert b2.build().amount == 20


class TestDataclassBuilder:
    def test_build_creates_dataclass(self) -> None:
        p = PointBuilder().build()
        assert isinstance(p, Point)
        assert p.x == 0.0
        assert p.y == 0.0

    def test_with_overrides_fields(self) -> None:
        p = PointBuilder().with_(x=3.0, y=4.0).build()
        assert p.x == 3.0
        assert p.y == 4.0

    def test_default_point_unchanged_after_derivation(self) -> None:
        origin = PointBuilder()
        shifted = origin.with_(x=1.0)
        assert origin.build().x == 0.0
        assert shifted.build().x == 1.0

    def test_call_convenience(self) -> None:
        p = PointBuilder()(x=5.0, y=6.0)
        assert p.x == 5.0 and p.y == 6.0

    def test_exported_from_generators_package(self) -> None:
        from mp_commons.testing.generators import Builder as B, DataclassBuilder as DCB

        assert B is Builder
        assert DCB is DataclassBuilder

    def test_exported_from_testing_package(self) -> None:
        from mp_commons.testing import Builder as B, DataclassBuilder as DCB

        assert B is Builder
        assert DCB is DataclassBuilder
