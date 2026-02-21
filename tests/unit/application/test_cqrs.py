"""Unit tests for CQRS — §9: Commands, Queries, Events."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from mp_commons.application.cqrs import (
    Command,
    CommandHandler,
    InProcessCommandBus,
    InProcessEventBus,
    InProcessQueryBus,
    Query,
    QueryHandler,
    EventHandler,
)
from mp_commons.kernel.ddd import DomainEvent
from mp_commons.kernel.types import EntityId


# ---------------------------------------------------------------------------
# Concrete commands / queries / events for tests
# ---------------------------------------------------------------------------


class CreateOrder(Command):
    def __init__(self, item: str) -> None:
        self.item = item


class GetOrder(Query):
    def __init__(self, order_id: str) -> None:
        self.order_id = order_id


class OrderCreated(DomainEvent):
    aggregate_id: str = "agg-1"
    event_type: str = "OrderCreated"


class CreateOrderHandler(CommandHandler[CreateOrder]):
    def __init__(self) -> None:
        self.handled: list[str] = []

    async def handle(self, command: CreateOrder) -> None:
        self.handled.append(command.item)


class GetOrderHandler(QueryHandler[GetOrder, dict]):
    async def handle(self, query: GetOrder) -> dict:
        return {"id": query.order_id, "item": "widget"}


class OrderCreatedHandler(EventHandler[OrderCreated]):
    def __init__(self) -> None:
        self.received: list[OrderCreated] = []

    async def handle(self, event: OrderCreated) -> None:
        self.received.append(event)


# ---------------------------------------------------------------------------
# CommandBus (9.1–9.4)
# ---------------------------------------------------------------------------


class TestInProcessCommandBus:
    def test_dispatch_invokes_handler(self) -> None:
        bus = InProcessCommandBus()
        handler = CreateOrderHandler()
        bus.register(CreateOrder, handler)

        asyncio.run(bus.dispatch(CreateOrder("apple")))
        assert handler.handled == ["apple"]

    def test_unregistered_command_raises(self) -> None:
        bus = InProcessCommandBus()
        with pytest.raises((KeyError, Exception)):
            asyncio.run(bus.dispatch(CreateOrder("apple")))

    def test_dispatch_multiple_calls(self) -> None:
        bus = InProcessCommandBus()
        handler = CreateOrderHandler()
        bus.register(CreateOrder, handler)

        async def _run() -> None:
            for item in ["a", "b", "c"]:
                await bus.dispatch(CreateOrder(item))

        asyncio.run(_run())
        assert handler.handled == ["a", "b", "c"]

    def test_last_registered_handler_wins(self) -> None:
        bus = InProcessCommandBus()
        h1 = CreateOrderHandler()
        h2 = CreateOrderHandler()
        bus.register(CreateOrder, h1)
        bus.register(CreateOrder, h2)

        asyncio.run(bus.dispatch(CreateOrder("x")))
        assert h2.handled == ["x"]
        assert h1.handled == []


# ---------------------------------------------------------------------------
# QueryBus (9.5)
# ---------------------------------------------------------------------------


class TestInProcessQueryBus:
    def test_ask_returns_handler_result(self) -> None:
        bus = InProcessQueryBus()
        bus.register(GetOrder, GetOrderHandler())
        result = asyncio.run(bus.ask(GetOrder("order-1")))
        assert result == {"id": "order-1", "item": "widget"}

    def test_unregistered_query_raises(self) -> None:
        bus = InProcessQueryBus()
        with pytest.raises((KeyError, Exception)):
            asyncio.run(bus.ask(GetOrder("order-1")))

    def test_different_query_types_independent(self) -> None:
        class AnotherQuery(Query):
            pass

        bus = InProcessQueryBus()
        bus.register(GetOrder, GetOrderHandler())
        with pytest.raises((KeyError, Exception)):
            asyncio.run(bus.ask(AnotherQuery()))


# ---------------------------------------------------------------------------
# EventBus (9.8–9.9)
# ---------------------------------------------------------------------------


class TestInProcessEventBus:
    def _make_event(self) -> OrderCreated:
        return OrderCreated(
            event_id=EntityId.generate(),
            occurred_at=datetime.now(UTC),
        )

    def test_single_handler_receives_event(self) -> None:
        bus = InProcessEventBus()
        handler = OrderCreatedHandler()
        bus.register(OrderCreated, handler)

        event = self._make_event()
        asyncio.run(bus.publish(event))
        assert len(handler.received) == 1
        assert handler.received[0] is event

    def test_multiple_handlers_all_receive(self) -> None:
        bus = InProcessEventBus()
        h1 = OrderCreatedHandler()
        h2 = OrderCreatedHandler()
        bus.register(OrderCreated, h1)
        bus.register(OrderCreated, h2)

        event = self._make_event()
        asyncio.run(bus.publish(event))
        assert len(h1.received) == 1
        assert len(h2.received) == 1

    def test_no_handlers_publish_is_noop(self) -> None:
        bus = InProcessEventBus()
        event = self._make_event()
        asyncio.run(bus.publish(event))  # must not raise

    def test_unrelated_event_not_delivered(self) -> None:
        class OtherEvent(DomainEvent):
            aggregate_id: str = "x"
            event_type: str = "Other"

        bus = InProcessEventBus()
        handler = OrderCreatedHandler()
        bus.register(OrderCreated, handler)

        other = OtherEvent(event_id=EntityId.generate(), occurred_at=datetime.now(UTC))
        asyncio.run(bus.publish(other))
        assert handler.received == []


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.application.cqrs")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing"


# ---------------------------------------------------------------------------
# MiddlewareAwareCommandBus (§9.6)
# ---------------------------------------------------------------------------


class TestMiddlewareAwareCommandBus:
    def test_dispatches_command_to_handler(self) -> None:
        from mp_commons.application.cqrs import MiddlewareAwareCommandBus
        from mp_commons.application.pipeline import Pipeline

        handler = CreateOrderHandler()
        bus = MiddlewareAwareCommandBus(Pipeline())
        bus.register(CreateOrder, handler)

        asyncio.run(bus.dispatch(CreateOrder("banana")))
        assert handler.handled == ["banana"]

    def test_middleware_is_invoked(self) -> None:
        from mp_commons.application.cqrs import MiddlewareAwareCommandBus
        from mp_commons.application.pipeline import Middleware, Pipeline

        touched: list[str] = []

        class _TouchMiddleware(Middleware):
            async def __call__(self, request: object, next_: object) -> object:  # type: ignore[override]
                touched.append("before")
                result = await next_(request)  # type: ignore[operator]
                touched.append("after")
                return result

        handler = CreateOrderHandler()
        bus = MiddlewareAwareCommandBus(Pipeline().add(_TouchMiddleware()))
        bus.register(CreateOrder, handler)

        asyncio.run(bus.dispatch(CreateOrder("cherry")))
        assert touched == ["before", "after"]
        assert handler.handled == ["cherry"]

    def test_unregistered_command_raises_key_error(self) -> None:
        from mp_commons.application.cqrs import MiddlewareAwareCommandBus
        from mp_commons.application.pipeline import Pipeline

        bus = MiddlewareAwareCommandBus(Pipeline())
        with pytest.raises(KeyError, match="CreateOrder"):
            asyncio.run(bus.dispatch(CreateOrder("x")))

    def test_returns_handler_result(self) -> None:
        from mp_commons.application.cqrs import MiddlewareAwareCommandBus, QueryHandler
        from mp_commons.application.pipeline import Pipeline

        class EchoHandler(CommandHandler[CreateOrder]):
            async def handle(self, command: CreateOrder) -> str:
                return f"echo:{command.item}"

        bus = MiddlewareAwareCommandBus(Pipeline())
        bus.register(CreateOrder, EchoHandler())

        result = asyncio.run(bus.dispatch(CreateOrder("echo-me")))
        assert result == "echo:echo-me"

    def test_multiple_commands_independently_dispatched(self) -> None:
        from mp_commons.application.cqrs import Command, MiddlewareAwareCommandBus
        from mp_commons.application.pipeline import Pipeline

        class CancelOrder(Command):
            def __init__(self, order_id: str) -> None:
                self.order_id = order_id

        class CancelOrderHandler(CommandHandler[CancelOrder]):
            def __init__(self) -> None:
                self.cancelled: list[str] = []

            async def handle(self, command: CancelOrder) -> None:
                self.cancelled.append(command.order_id)

        create_handler = CreateOrderHandler()
        cancel_handler = CancelOrderHandler()

        bus = MiddlewareAwareCommandBus(Pipeline())
        bus.register(CreateOrder, create_handler)
        bus.register(CancelOrder, cancel_handler)

        async def _run() -> None:
            await bus.dispatch(CreateOrder("grape"))
            await bus.dispatch(CancelOrder("order-99"))

        asyncio.run(_run())
        assert create_handler.handled == ["grape"]
        assert cancel_handler.cancelled == ["order-99"]
