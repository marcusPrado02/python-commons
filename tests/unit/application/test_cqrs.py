"""Unit tests for CQRS — InProcessCommandBus and InProcessQueryBus."""

from __future__ import annotations

import pytest

from mp_commons.application.cqrs import (
    Command,
    CommandHandler,
    InProcessCommandBus,
    InProcessQueryBus,
    Query,
    QueryHandler,
)
from mp_commons.kernel.errors import ApplicationError


# ---------------------------------------------------------------------------
# Concrete commands / queries
# ---------------------------------------------------------------------------


class CreateOrder(Command):
    def __init__(self, item: str) -> None:
        self.item = item


class GetOrder(Query):
    def __init__(self, order_id: str) -> None:
        self.order_id = order_id


class CreateOrderHandler(CommandHandler[CreateOrder]):
    def __init__(self) -> None:
        self.handled: list[str] = []

    async def handle(self, command: CreateOrder) -> None:
        self.handled.append(command.item)


class GetOrderHandler(QueryHandler[GetOrder, dict]):
    async def handle(self, query: GetOrder) -> dict:
        return {"id": query.order_id, "item": "widget"}


# ---------------------------------------------------------------------------
# CommandBus
# ---------------------------------------------------------------------------


class TestInProcessCommandBus:
    @pytest.mark.asyncio
    async def test_dispatch_invokes_handler(self) -> None:
        bus = InProcessCommandBus()
        handler = CreateOrderHandler()
        bus.register(CreateOrder, handler)

        await bus.dispatch(CreateOrder("apple"))
        assert handler.handled == ["apple"]

    @pytest.mark.asyncio
    async def test_unregistered_command_raises(self) -> None:
        bus = InProcessCommandBus()
        with pytest.raises((KeyError, ApplicationError)):
            await bus.dispatch(CreateOrder("apple"))

    @pytest.mark.asyncio
    async def test_dispatch_multiple_calls(self) -> None:
        bus = InProcessCommandBus()
        handler = CreateOrderHandler()
        bus.register(CreateOrder, handler)

        for item in ["a", "b", "c"]:
            await bus.dispatch(CreateOrder(item))

        assert handler.handled == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# QueryBus
# ---------------------------------------------------------------------------


class TestInProcessQueryBus:
    @pytest.mark.asyncio
    async def test_ask_returns_handler_result(self) -> None:
        bus = InProcessQueryBus()
        bus.register(GetOrder, GetOrderHandler())
        result = await bus.ask(GetOrder("order-1"))
        assert result == {"id": "order-1", "item": "widget"}

    @pytest.mark.asyncio
    async def test_unregistered_query_raises(self) -> None:
        bus = InProcessQueryBus()
        with pytest.raises((KeyError, ApplicationError)):
            await bus.ask(GetOrder("order-1"))
