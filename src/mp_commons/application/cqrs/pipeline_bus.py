"""CQRS – MiddlewareAwareCommandBus: dispatches via a Pipeline (§9.6).

Usage::

    bus = MiddlewareAwareCommandBus(
        Pipeline()
        .add(LoggingMiddleware())
        .add(AuthzMiddleware(policy_engine))
        .add(RetryMiddleware(max_attempts=3))
    )
    bus.register(CreateOrder, CreateOrderHandler())
    result = await bus.dispatch(CreateOrder(item="widget"))
"""
from __future__ import annotations

from typing import Any

from mp_commons.application.cqrs.commands import Command, CommandBus, CommandHandler
from mp_commons.application.pipeline.pipeline import Pipeline


class MiddlewareAwareCommandBus(CommandBus):
    """Command bus that routes every dispatch through a middleware Pipeline.

    Each registered handler is invoked as the *terminal* handler of the
    pipeline, giving middleware full visibility into the request and result.
    """

    def __init__(self, pipeline: Pipeline) -> None:
        self._pipeline = pipeline
        self._handlers: dict[type[Command], CommandHandler[Any]] = {}

    # ------------------------------------------------------------------
    # CommandBus interface
    # ------------------------------------------------------------------

    def register(self, command_type: type[Command], handler: CommandHandler[Any]) -> None:
        """Register *handler* for *command_type*."""
        self._handlers[command_type] = handler

    async def dispatch(self, command: Command) -> Any:
        """Run *command* through the pipeline then invoke its handler."""
        handler = self._handlers.get(type(command))
        if handler is None:
            raise KeyError(f"No handler registered for {type(command).__name__!r}")
        return await self._pipeline.execute(command, handler.handle)


__all__ = ["MiddlewareAwareCommandBus"]
