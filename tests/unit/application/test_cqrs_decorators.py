"""Tests for §9.10 – @command_handler / @query_handler auto-registration decorators."""
from __future__ import annotations

import dataclasses
import pytest

from mp_commons.application.cqrs import (
    Command,
    CommandHandler,
    InProcessCommandBus,
    InProcessQueryBus,
    Query,
    QueryHandler,
    clear_registries,
    command_handler,
    make_command_bus,
    make_query_bus,
    query_handler,
)
from mp_commons.application.cqrs.decorators import _COMMAND_REGISTRY, _QUERY_REGISTRY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class _AddCmd(Command):
    value: int


class _Result:
    def __init__(self, value: int) -> None:
        self.value = value


@dataclasses.dataclass
class _FindQuery(Query):
    key: str


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registries():
    """Reset global registries before (and after) every test."""
    clear_registries()
    yield
    clear_registries()


# ---------------------------------------------------------------------------
# @command_handler
# ---------------------------------------------------------------------------


class TestCommandHandlerDecorator:
    def test_registers_handler_class(self) -> None:
        @command_handler(_AddCmd)
        class _H(CommandHandler[_AddCmd]):
            async def handle(self, cmd: _AddCmd) -> None:
                pass

        assert _COMMAND_REGISTRY[_AddCmd] is _H

    def test_returns_handler_class_unchanged(self) -> None:
        @command_handler(_AddCmd)
        class _H(CommandHandler[_AddCmd]):
            async def handle(self, cmd: _AddCmd) -> None:
                pass

        assert _H.__name__ == "_H"

    def test_make_command_bus_returns_inprocess_bus(self) -> None:
        @command_handler(_AddCmd)
        class _H(CommandHandler[_AddCmd]):
            async def handle(self, cmd: _AddCmd) -> None:
                pass

        bus = make_command_bus()
        assert isinstance(bus, InProcessCommandBus)

    def test_make_command_bus_dispatches_correctly(self) -> None:
        received: list[int] = []

        @command_handler(_AddCmd)
        class _H(CommandHandler[_AddCmd]):
            async def handle(self, cmd: _AddCmd) -> None:
                received.append(cmd.value)

        bus = make_command_bus()

        import asyncio
        asyncio.run(bus.dispatch(_AddCmd(value=42)))
        assert received == [42]

    def test_extra_handlers_override_registry(self) -> None:
        @command_handler(_AddCmd)
        class _H1(CommandHandler[_AddCmd]):
            async def handle(self, cmd: _AddCmd) -> None:
                pass

        class _H2(CommandHandler[_AddCmd]):
            async def handle(self, cmd: _AddCmd) -> None:
                pass

        bus = make_command_bus(extra={_AddCmd: _H2()})
        assert isinstance(bus, InProcessCommandBus)

    def test_clear_registries_resets_command_registry(self) -> None:
        @command_handler(_AddCmd)
        class _H(CommandHandler[_AddCmd]):
            async def handle(self, cmd: _AddCmd) -> None:
                pass

        assert _AddCmd in _COMMAND_REGISTRY
        clear_registries()
        assert _AddCmd not in _COMMAND_REGISTRY


# ---------------------------------------------------------------------------
# @query_handler
# ---------------------------------------------------------------------------


class TestQueryHandlerDecorator:
    def test_registers_handler_class(self) -> None:
        @query_handler(_FindQuery)
        class _H(QueryHandler[_FindQuery, _Result]):
            async def handle(self, query: _FindQuery) -> _Result:
                return _Result(0)

        assert _QUERY_REGISTRY[_FindQuery] is _H

    def test_returns_handler_class_unchanged(self) -> None:
        @query_handler(_FindQuery)
        class _H(QueryHandler[_FindQuery, _Result]):
            async def handle(self, query: _FindQuery) -> _Result:
                return _Result(0)

        assert _H.__name__ == "_H"

    def test_make_query_bus_returns_inprocess_bus(self) -> None:
        @query_handler(_FindQuery)
        class _H(QueryHandler[_FindQuery, _Result]):
            async def handle(self, query: _FindQuery) -> _Result:
                return _Result(0)

        bus = make_query_bus()
        assert isinstance(bus, InProcessQueryBus)

    def test_make_query_bus_dispatches_correctly(self) -> None:
        @query_handler(_FindQuery)
        class _H(QueryHandler[_FindQuery, _Result]):
            async def handle(self, query: _FindQuery) -> _Result:
                return _Result(99)

        bus = make_query_bus()
        import asyncio
        result = asyncio.run(bus.ask(_FindQuery(key="x")))
        assert isinstance(result, _Result)
        assert result.value == 99

    def test_clear_registries_resets_query_registry(self) -> None:
        @query_handler(_FindQuery)
        class _H(QueryHandler[_FindQuery, _Result]):
            async def handle(self, query: _FindQuery) -> _Result:
                return _Result(0)

        assert _FindQuery in _QUERY_REGISTRY
        clear_registries()
        assert _FindQuery not in _QUERY_REGISTRY
