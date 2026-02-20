"""Saga base — long-running process manager correlated by saga_id."""

from __future__ import annotations

import abc
from typing import Any, Callable, Coroutine

from mp_commons.kernel.ddd.domain_event import DomainEvent
from mp_commons.kernel.types.ids import EntityId

#: Type alias for an async saga step handler.
SagaHandler = Callable[[DomainEvent], Coroutine[Any, Any, None]]


class Saga(abc.ABC):
    """Base class for sagas (long-running process managers).

    A saga reacts to a sequence of ``DomainEvent`` instances and
    coordinates multi-step workflows that span multiple aggregates.

    Subclasses should:
    1. Register step handlers in ``__init__`` via :meth:`_register`.
    2. Call :meth:`_mark_completed` when the process is done.

    The saga is correlated by ``saga_id`` so that incoming events can be
    routed to the correct in-flight instance.

    Example::

        class OrderFulfillmentSaga(Saga):
            def __init__(self, saga_id: EntityId) -> None:
                super().__init__(saga_id)
                self._register(PaymentConfirmed, self._on_payment)
                self._register(WarehousePicked, self._on_picked)

            async def _on_payment(self, event: PaymentConfirmed) -> None:
                # trigger warehouse pick
                ...

            async def _on_picked(self, event: WarehousePicked) -> None:
                # trigger shipping
                self._mark_completed()
    """

    def __init__(self, saga_id: EntityId) -> None:
        self._saga_id = saga_id
        self._completed: bool = False
        self._handlers: dict[type[DomainEvent], SagaHandler] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def saga_id(self) -> EntityId:
        """Correlation identifier for this saga instance."""
        return self._saga_id

    @property
    def completed(self) -> bool:
        """``True`` once :meth:`_mark_completed` has been called."""
        return self._completed

    async def handle(self, event: DomainEvent) -> None:
        """Route *event* to the registered handler, if any."""
        handler = self._handlers.get(type(event))
        if handler is not None:
            await handler(event)

    # ------------------------------------------------------------------
    # Protected helpers for subclasses
    # ------------------------------------------------------------------

    def _register(
        self,
        event_type: type[DomainEvent],
        handler: SagaHandler,
    ) -> None:
        """Register *handler* as the step for *event_type*."""
        self._handlers[event_type] = handler

    def _mark_completed(self) -> None:
        """Signal that this saga instance has finished."""
        self._completed = True


__all__ = ["Saga", "SagaHandler"]
