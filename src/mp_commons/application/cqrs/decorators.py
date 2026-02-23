"""Application CQRS – @command_handler and @query_handler auto-registration decorators (§9.10)."""
from __future__ import annotations

from typing import Any

from mp_commons.application.cqrs.commands import Command, CommandHandler, InProcessCommandBus
from mp_commons.application.cqrs.queries import Query, QueryHandler, InProcessQueryBus

# ---------------------------------------------------------------------------
# Global registries populated at import time by the decorators
# ---------------------------------------------------------------------------

_COMMAND_REGISTRY: dict[type[Command], type[CommandHandler[Any]]] = {}
_QUERY_REGISTRY: dict[type[Query], type[QueryHandler[Any, Any]]] = {}


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def command_handler(command_type: type[Command]):
    """Class decorator that registers a :class:`CommandHandler` for the given
    command type in the global command registry.

    Usage::

        @command_handler(CreateOrder)
        class CreateOrderHandler(CommandHandler[CreateOrder]):
            async def handle(self, command: CreateOrder) -> None:
                ...

    The handler is instantiated (no-arg constructor) when a bus is built via
    :func:`make_command_bus`.
    """
    def decorator(handler_class: type[CommandHandler[Any]]) -> type[CommandHandler[Any]]:
        _COMMAND_REGISTRY[command_type] = handler_class
        return handler_class

    return decorator


def query_handler(query_type: type[Query]):
    """Class decorator that registers a :class:`QueryHandler` for the given
    query type in the global query registry.

    Usage::

        @query_handler(GetOrderById)
        class GetOrderByIdHandler(QueryHandler[GetOrderById, Order]):
            async def handle(self, query: GetOrderById) -> Order:
                ...
    """
    def decorator(handler_class: type[QueryHandler[Any, Any]]) -> type[QueryHandler[Any, Any]]:
        _QUERY_REGISTRY[query_type] = handler_class
        return handler_class

    return decorator


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_command_bus(
    extra: dict[type[Command], CommandHandler[Any]] | None = None,
) -> InProcessCommandBus:
    """Instantiate an :class:`InProcessCommandBus` pre-populated from the
    global command registry.

    *extra* allows callers to inject additional (or override) handlers without
    touching the global registry – useful in tests.
    """
    bus = InProcessCommandBus()
    for cmd_type, handler_class in _COMMAND_REGISTRY.items():
        bus.register(cmd_type, handler_class())
    if extra:
        for cmd_type, handler_instance in extra.items():
            bus.register(cmd_type, handler_instance)
    return bus


def make_query_bus(
    extra: dict[type[Query], QueryHandler[Any, Any]] | None = None,
) -> InProcessQueryBus:
    """Instantiate an :class:`InProcessQueryBus` pre-populated from the global
    query registry.
    """
    bus = InProcessQueryBus()
    for query_type, handler_class in _QUERY_REGISTRY.items():
        bus.register(query_type, handler_class())
    if extra:
        for query_type, handler_instance in extra.items():
            bus.register(query_type, handler_instance)
    return bus


def clear_registries() -> None:
    """Clear both global registries.  Use in tests to avoid inter-test leakage.

    .. warning::
        This mutates module-level state.  Only call in tests.
    """
    _COMMAND_REGISTRY.clear()
    _QUERY_REGISTRY.clear()


__all__ = [
    "clear_registries",
    "command_handler",
    "make_command_bus",
    "make_query_bus",
    "query_handler",
]
