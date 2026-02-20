"""Application CQRS – Query, QueryHandler, QueryBus, InProcessQueryBus."""
from __future__ import annotations

import abc
from typing import Any, Generic, TypeVar

Q = TypeVar("Q", bound="Query")
R = TypeVar("R")


class Query:
    """Marker base for queries (read-only intent)."""


class QueryHandler(abc.ABC, Generic[Q, R]):
    """Handle a single query type and return a result."""

    @abc.abstractmethod
    async def handle(self, query: Q) -> R: ...


class QueryBus(abc.ABC):
    """Dispatches queries to their registered handlers."""

    @abc.abstractmethod
    def register(self, query_type: type[Query], handler: QueryHandler[Any, Any]) -> None: ...

    @abc.abstractmethod
    async def ask(self, query: Query) -> Any: ...


class InProcessQueryBus(QueryBus):
    """In-process query bus."""

    def __init__(self) -> None:
        self._handlers: dict[type[Query], QueryHandler[Any, Any]] = {}

    def register(self, query_type: type[Query], handler: QueryHandler[Any, Any]) -> None:
        self._handlers[query_type] = handler

    async def ask(self, query: Query) -> Any:
        handler = self._handlers.get(type(query))
        if handler is None:
            raise KeyError(f"No handler registered for {type(query).__name__!r}")
        return await handler.handle(query)


__all__ = ["InProcessQueryBus", "Query", "QueryBus", "QueryHandler"]
