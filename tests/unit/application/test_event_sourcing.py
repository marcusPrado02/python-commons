"""Unit tests for Event Sourcing (§44)."""

from __future__ import annotations

import asyncio
import dataclasses
import json

import pytest

from mp_commons.application.event_sourcing import (
    EventSourcedAggregate,
    EventSourcedRepository,
    EventStore,
    InMemoryEventStore,
    InMemorySnapshotStore,
    OptimisticConcurrencyError,
    Projector,
    SnapshotRecord,
    SnapshotStore,
    StoredEvent,
)
from mp_commons.kernel.ddd.domain_event import DomainEvent
from mp_commons.kernel.types.ids import EntityId


# ---------------------------------------------------------------------------
# Shared test fixtures — Order aggregate
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class OrderPlaced(DomainEvent):
    order_id: str


@dataclasses.dataclass(frozen=True)
class OrderCancelled(DomainEvent):
    order_id: str
    reason: str = ""


class Order(EventSourcedAggregate):
    """Minimal event-sourced aggregate used in tests."""

    def __init__(self, id: EntityId) -> None:
        super().__init__(id)
        self.placed: bool = False
        self.cancelled: bool = False

    @classmethod
    def stream_prefix(cls) -> str:
        return "Order"

    def apply_stored_event(self, event: StoredEvent) -> None:
        if event.event_type == "OrderPlaced":
            self.placed = True
        elif event.event_type == "OrderCancelled":
            self.cancelled = True

    def place(self) -> None:
        self._raise_event(OrderPlaced(order_id=str(self.id)))

    def cancel(self, reason: str = "") -> None:
        self._raise_event(OrderCancelled(order_id=str(self.id), reason=reason))


def _order_id(value: str = "order-1") -> EntityId:
    return EntityId(value)


def _event(
    stream_id: str = "Order-order-1",
    version: int = 1,
    event_type: str = "OrderPlaced",
    payload: bytes = b"{}",
) -> StoredEvent:
    return StoredEvent(
        stream_id=stream_id,
        version=version,
        event_type=event_type,
        payload=payload,
    )


class OrderRepository(EventSourcedRepository["Order", EntityId]):
    def _aggregate_class(self) -> type[Order]:
        return Order

    def _create_empty(self, agg_id: EntityId) -> Order:
        return Order(agg_id)


# ---------------------------------------------------------------------------
# §44.2  StoredEvent
# ---------------------------------------------------------------------------


class TestStoredEvent:
    def test_required_fields(self) -> None:
        ev = StoredEvent(
            stream_id="Order-1",
            version=1,
            event_type="OrderPlaced",
            payload=b'{"order_id": "1"}',
        )
        assert ev.stream_id == "Order-1"
        assert ev.version == 1
        assert ev.event_type == "OrderPlaced"
        assert ev.payload == b'{"order_id": "1"}'

    def test_metadata_defaults_to_empty_dict(self) -> None:
        ev = _event()
        assert ev.metadata == {}

    def test_with_metadata(self) -> None:
        ev = StoredEvent(
            stream_id="s", version=1, event_type="E", payload=b"{}",
            metadata={"correlation_id": "abc"},
        )
        assert ev.metadata["correlation_id"] == "abc"

    def test_occurred_at_is_set(self) -> None:
        ev = _event()
        assert ev.occurred_at is not None

    def test_is_frozen(self) -> None:
        ev = _event()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            ev.version = 99  # type: ignore[misc]

    def test_stored_events_with_same_data_are_equal(self) -> None:
        from datetime import UTC, datetime
        ts = datetime(2025, 1, 1, tzinfo=UTC)
        e1 = StoredEvent("s", 1, "E", b"{}", {}, ts)
        e2 = StoredEvent("s", 1, "E", b"{}", {}, ts)
        assert e1 == e2


# ---------------------------------------------------------------------------
# §44.6  InMemoryEventStore
# ---------------------------------------------------------------------------


class TestInMemoryEventStore:
    def test_append_and_load(self) -> None:
        store = InMemoryEventStore()
        ev = _event()

        async def run() -> list[StoredEvent]:
            await store.append("Order-order-1", [ev], expected_version=0)
            return await store.load("Order-order-1")

        events = asyncio.run(run())
        assert len(events) == 1
        assert events[0].event_type == "OrderPlaced"

    def test_load_empty_stream_returns_empty_list(self) -> None:
        store = InMemoryEventStore()
        events = asyncio.run(store.load("nonexistent"))
        assert events == []

    def test_optimistic_concurrency_error_on_version_mismatch(self) -> None:
        store = InMemoryEventStore()

        async def run() -> None:
            await store.append("s", [_event(stream_id="s", version=1)], 0)
            # Wrong expected_version (should be 1, not 0)
            await store.append("s", [_event(stream_id="s", version=2)], 0)

        with pytest.raises(OptimisticConcurrencyError) as exc_info:
            asyncio.run(run())

        err = exc_info.value
        assert err.stream_id == "s"
        assert err.expected == 0
        assert err.actual == 1

    def test_append_multiple_events(self) -> None:
        store = InMemoryEventStore()
        events = [
            _event(stream_id="s", version=i + 1, event_type=f"E{i}")
            for i in range(3)
        ]

        async def run() -> list[StoredEvent]:
            await store.append("s", events, 0)
            return await store.load("s")

        loaded = asyncio.run(run())
        assert len(loaded) == 3
        assert [e.event_type for e in loaded] == ["E0", "E1", "E2"]

    def test_load_from_version_filters(self) -> None:
        store = InMemoryEventStore()
        events = [_event(stream_id="s", version=i + 1) for i in range(5)]

        async def run() -> list[StoredEvent]:
            await store.append("s", events, 0)
            return await store.load("s", from_version=3)

        loaded = asyncio.run(run())
        assert len(loaded) == 2
        assert loaded[0].version == 4
        assert loaded[1].version == 5

    def test_stream_version(self) -> None:
        store = InMemoryEventStore()

        async def run() -> int:
            await store.append("s", [_event(stream_id="s", version=1)], 0)
            return store.stream_version("s")

        assert asyncio.run(run()) == 1

    def test_all_events(self) -> None:
        store = InMemoryEventStore()

        async def run() -> list[StoredEvent]:
            await store.append("a", [_event(stream_id="a", version=1)], 0)
            await store.append("b", [_event(stream_id="b", version=1)], 0)
            return store.all_events()

        all_ev = asyncio.run(run())
        assert len(all_ev) == 2

    def test_is_subclass_of_event_store(self) -> None:
        assert issubclass(InMemoryEventStore, EventStore)

    def test_correct_version_after_sequential_appends(self) -> None:
        store = InMemoryEventStore()

        async def run() -> None:
            await store.append("s", [_event(stream_id="s", version=1)], 0)
            await store.append("s", [_event(stream_id="s", version=2)], 1)
            await store.append("s", [_event(stream_id="s", version=3)], 2)

        asyncio.run(run())
        assert store.stream_version("s") == 3


# ---------------------------------------------------------------------------
# §44.1 / §44.5 (EventStore abstract) + OptimisticConcurrencyError
# ---------------------------------------------------------------------------


class TestOptimisticConcurrencyError:
    def test_message_contains_stream_id(self) -> None:
        err = OptimisticConcurrencyError("my-stream", 2, 5)
        assert "my-stream" in str(err)
        assert "2" in str(err)
        assert "5" in str(err)

    def test_attributes(self) -> None:
        err = OptimisticConcurrencyError("s", 1, 3)
        assert err.stream_id == "s"
        assert err.expected == 1
        assert err.actual == 3


# ---------------------------------------------------------------------------
# §44  EventSourcedAggregate
# ---------------------------------------------------------------------------


class TestEventSourcedAggregate:
    def test_stream_prefix_defaults_to_class_name(self) -> None:
        assert Order.stream_prefix() == "Order"

    def test_stream_id_for(self) -> None:
        oid = _order_id("abc")
        assert Order.stream_id_for(oid) == "Order-abc"

    def test_apply_placed_event(self) -> None:
        order = Order(_order_id())
        ev = _event(event_type="OrderPlaced")
        order.apply_stored_event(ev)
        assert order.placed is True

    def test_apply_cancelled_event(self) -> None:
        order = Order(_order_id())
        ev = _event(event_type="OrderCancelled")
        order.apply_stored_event(ev)
        assert order.cancelled is True

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            EventSourcedAggregate(EntityId("x"))  # type: ignore[abstract]

    def test_is_subclass_of_aggregate_root(self) -> None:
        from mp_commons.kernel.ddd.aggregate import AggregateRoot
        assert issubclass(Order, AggregateRoot)

    def test_raise_event_increments_version(self) -> None:
        order = Order(_order_id())
        assert order.version == 0
        order.place()
        assert order.version == 1


# ---------------------------------------------------------------------------
# §44.3  EventSourcedRepository
# ---------------------------------------------------------------------------


class TestEventSourcedRepository:
    def test_load_returns_none_for_unknown_aggregate(self) -> None:
        repo = OrderRepository(store=InMemoryEventStore())
        result = asyncio.run(repo.load(_order_id("unknown")))
        assert result is None

    def test_save_and_load_round_trip(self) -> None:
        store = InMemoryEventStore()
        repo = OrderRepository(store=store)
        oid = _order_id("order-42")

        async def run() -> Order | None:
            order = Order(oid)
            order.place()
            await repo.save(order)
            return await repo.load(oid)

        loaded = asyncio.run(run())
        assert loaded is not None
        assert loaded.placed is True

    def test_save_no_events_does_nothing(self) -> None:
        store = InMemoryEventStore()
        repo = OrderRepository(store=store)
        order = Order(_order_id())
        asyncio.run(repo.save(order))
        assert store.stream_version(Order.stream_id_for(order.id)) == 0  # type: ignore[arg-type]

    def test_multiple_events_replayed_in_order(self) -> None:
        store = InMemoryEventStore()
        repo = OrderRepository(store=store)
        oid = _order_id("order-m")

        async def run() -> Order | None:
            order = Order(oid)
            order.place()
            order.cancel(reason="changed mind")
            await repo.save(order)
            return await repo.load(oid)

        loaded = asyncio.run(run())
        assert loaded is not None
        assert loaded.placed is True
        assert loaded.cancelled is True

    def test_version_is_restored_after_load(self) -> None:
        store = InMemoryEventStore()
        repo = OrderRepository(store=store)
        oid = _order_id("order-v")

        async def run() -> Order | None:
            order = Order(oid)
            order.place()
            await repo.save(order)
            return await repo.load(oid)

        loaded = asyncio.run(run())
        assert loaded is not None
        assert loaded.version == 1

    def test_incrementally_save_raises_optimistic_locking_on_conflict(self) -> None:
        """Two saves without reload should raise OptimisticConcurrencyError."""
        store = InMemoryEventStore()
        repo = OrderRepository(store=store)
        oid = _order_id("order-c")

        async def run() -> None:
            order1 = Order(oid)
            order1.place()
            await repo.save(order1)
            # Create a "stale" copy that also thinks base version = 0
            order2 = Order(oid)
            order2.place()
            # order2._version is 1 after place(), prior = 1-1 = 0 → conflict
            await repo.save(order2)

        with pytest.raises(OptimisticConcurrencyError):
            asyncio.run(run())

    def test_custom_serialiser_is_used(self) -> None:
        serialised_payloads: list[bytes] = []

        def my_serialiser(event: DomainEvent) -> bytes:
            serialised_payloads.append(b"custom")
            return b"custom"

        store = InMemoryEventStore()
        repo = OrderRepository(store=store, serialise=my_serialiser)
        order = Order(_order_id("custom-ser"))
        order.place()
        asyncio.run(repo.save(order))
        assert b"custom" in serialised_payloads


# ---------------------------------------------------------------------------
# §44.4  SnapshotStore + InMemorySnapshotStore
# ---------------------------------------------------------------------------


class TestInMemorySnapshotStore:
    def test_take_and_latest(self) -> None:
        snap_store = InMemorySnapshotStore()

        async def run() -> SnapshotRecord | None:
            await snap_store.take("Order-1", 5, b'{"placed": true}')
            return await snap_store.latest("Order-1")

        record = asyncio.run(run())
        assert record is not None
        assert record.version == 5
        assert record.state_bytes == b'{"placed": true}'

    def test_latest_returns_none_when_no_snapshot(self) -> None:
        snap_store = InMemorySnapshotStore()
        result = asyncio.run(snap_store.latest("nonexistent"))
        assert result is None

    def test_newer_snapshot_replaces_older(self) -> None:
        snap_store = InMemorySnapshotStore()

        async def run() -> SnapshotRecord | None:
            await snap_store.take("s1", 3, b"old")
            await snap_store.take("s1", 7, b"new")
            return await snap_store.latest("s1")

        record = asyncio.run(run())
        assert record is not None
        assert record.version == 7
        assert record.state_bytes == b"new"

    def test_snapshot_reduces_replay_event_count(self) -> None:
        """Illustrative integration: load only events after snapshot version."""
        store = InMemoryEventStore()
        snap_store = InMemorySnapshotStore()

        async def run() -> tuple[SnapshotRecord | None, list[StoredEvent]]:
            # Append 5 events
            events = [_event(stream_id="s", version=i + 1) for i in range(5)]
            await store.append("s", events, 0)
            # Take snapshot after version 3
            await snap_store.take("s", 3, b'{"partial": true}')
            # Load snapshot + only events after version 3
            snap = await snap_store.latest("s")
            from_v = snap.version if snap else 0
            tail = await store.load("s", from_version=from_v)
            return snap, tail

        snap, tail = asyncio.run(run())
        assert snap is not None
        assert snap.version == 3
        assert len(tail) == 2  # only versions 4 and 5
        assert tail[0].version == 4

    def test_is_subclass_of_snapshot_store(self) -> None:
        assert issubclass(InMemorySnapshotStore, SnapshotStore)

    def test_all_snapshots(self) -> None:
        snap_store = InMemorySnapshotStore()

        async def run() -> None:
            await snap_store.take("a", 1, b"a")
            await snap_store.take("b", 2, b"b")

        asyncio.run(run())
        snaps = snap_store.all_snapshots()
        assert set(snaps.keys()) == {"a", "b"}


# ---------------------------------------------------------------------------
# §44.5  Projector
# ---------------------------------------------------------------------------


class TestProjector:
    def test_project_single_event(self) -> None:
        class SummaryProjector(Projector[dict]):
            def __init__(self) -> None:
                self.events_seen: list[str] = []

            async def project(self, event: StoredEvent) -> None:
                self.events_seen.append(event.event_type)

        proj = SummaryProjector()
        asyncio.run(proj.project(_event(event_type="OrderPlaced")))
        assert proj.events_seen == ["OrderPlaced"]

    def test_project_all_in_order(self) -> None:
        class OrderProj(Projector[None]):
            def __init__(self) -> None:
                self.order: list[str] = []

            async def project(self, event: StoredEvent) -> None:
                self.order.append(event.event_type)

        proj = OrderProj()
        events = [_event(event_type=t) for t in ["A", "B", "C"]]
        asyncio.run(proj.project_all(events))
        assert proj.order == ["A", "B", "C"]

    def test_project_all_empty_list(self) -> None:
        class NoopProj(Projector[None]):
            async def project(self, event: StoredEvent) -> None: ...

        asyncio.run(NoopProj().project_all([]))  # must not raise

    def test_cannot_instantiate_abstract_projector(self) -> None:
        with pytest.raises(TypeError):
            Projector()  # type: ignore[abstract]

    def test_projector_can_build_state(self) -> None:
        class OrderStateProjector(Projector[dict]):
            def __init__(self) -> None:
                self.state: dict[str, bool] = {}

            async def project(self, event: StoredEvent) -> None:
                if event.event_type == "OrderPlaced":
                    self.state[event.stream_id] = True

        proj = OrderStateProjector()
        asyncio.run(proj.project(_event(stream_id="Order-1", event_type="OrderPlaced")))
        asyncio.run(proj.project(_event(stream_id="Order-2", event_type="OrderPlaced")))
        assert proj.state == {"Order-1": True, "Order-2": True}


# ---------------------------------------------------------------------------
# §44  __init__ exports
# ---------------------------------------------------------------------------


class TestEventSourcingInit:
    def test_all_public_names_importable(self) -> None:
        from mp_commons.application.event_sourcing import (
            EventSourcedAggregate,
            EventSourcedRepository,
            EventStore,
            InMemoryEventStore,
            InMemorySnapshotStore,
            OptimisticConcurrencyError,
            Projector,
            SnapshotRecord,
            SnapshotStore,
            StoredEvent,
        )
        for obj in (
            EventSourcedAggregate,
            EventSourcedRepository,
            EventStore,
            InMemoryEventStore,
            InMemorySnapshotStore,
            OptimisticConcurrencyError,
            Projector,
            SnapshotRecord,
            SnapshotStore,
            StoredEvent,
        ):
            assert obj is not None
