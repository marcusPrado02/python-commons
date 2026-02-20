"""Application CQRS – Command, CommandHandler, CommandBus, InProcessCommandBus."""
from __future__ import annotations

import abc
from typing import Any, Generic, TypeVar

C = TypeVar("C", bound="Command")


class Command:
    """Marker base for commands (intent to change state)."""


class CommandHandler(abc.ABC, Generic[C]):
    """Handle a single command type."""

    @abc.abstractmethod
    async def handle(self, command: C) -> Any: ...


class CommandBus(abc.ABC):
    """Dispatches commands to their registered handlers."""

    @abc.abstractmethod
    def register(self, command_type: type[Command], handler: CommandHandler[Any]) -> None: ...

    @abc.abstractmethod
    async def dispatch(self, command: Command) -> Any: ...


class InProcessCommandBus(CommandBus):
    """In-process command bus (synchronous registry, async dispatch)."""

    def __init__(self) -> None:
        self._handlers: dict[type[Command], CommandHandler[Any]] = {}

    def register(self, command_type: type[Command], handler: CommandHandler[Any]) -> None:
        self._handlers[command_type] = handler

    async def dispatch(self, command: Command) -> Any:
        handler = self._handlers.get(type(command))
        if handler is None:
            raise KeyError(f"No handler registered for {type(command).__name__!r}")
        return await handler.handle(command)


__all__ = ["Command", "CommandBus", "CommandHandler", "InProcessCommandBus"]
