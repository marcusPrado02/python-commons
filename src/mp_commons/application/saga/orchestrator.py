"""Application saga – SagaOrchestrator."""

from __future__ import annotations

from typing import Any

from mp_commons.application.saga.context import SagaContext
from mp_commons.application.saga.state import SagaState
from mp_commons.application.saga.step import SagaStep
from mp_commons.application.saga.store import SagaStore


class SagaOrchestrator:
    """Executes a list of :class:`SagaStep` objects in sequence.

    On success every step's :meth:`~SagaStep.action` is awaited in order.

    On failure the orchestrator switches to *compensation mode* and calls
    each already-completed step's :meth:`~SagaStep.compensate` in reverse
    order.  If a compensation step also raises, the saga ends in
    :attr:`~SagaState.COMPENSATION_FAILED`; otherwise it ends in
    :attr:`~SagaState.FAILED`.

    A :class:`~mp_commons.application.saga.store.SagaStore` is optional.
    When provided the saga state is persisted after every step so the saga
    can be resumed or inspected after a crash.

    Example::

        orchestrator = SagaOrchestrator(steps=[step_a, step_b], store=store)
        ctx = await orchestrator.run("order-123", initial={"order_id": "123"})
    """

    def __init__(
        self,
        steps: list[SagaStep],
        store: SagaStore | None = None,
    ) -> None:
        if not steps:
            raise ValueError("SagaOrchestrator requires at least one step")
        self._steps = steps
        self._store = store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        saga_id: str,
        initial: dict[str, Any] | None = None,
    ) -> SagaContext:
        """Run all steps and return the final :class:`SagaContext`.

        Raises :class:`SagaFailedError` when a step fails and all
        compensations succeed.

        Raises :class:`SagaCompensationFailedError` when both a step and
        at least one compensation step fail.
        """
        ctx = SagaContext(initial)
        completed: list[int] = []  # indices of successfully executed steps

        await self._persist(saga_id, SagaState.RUNNING, 0, ctx)

        # ---- forward pass ----
        for idx, step in enumerate(self._steps):
            try:
                await step.action(ctx)
                completed.append(idx)
                await self._persist(saga_id, SagaState.RUNNING, idx + 1, ctx)
            except Exception as action_exc:
                # Switch to compensation
                await self._persist(saga_id, SagaState.COMPENSATING, idx, ctx)
                compensation_exc = await self._compensate(
                    saga_id, ctx, completed
                )
                if compensation_exc is not None:
                    final_state = SagaState.COMPENSATION_FAILED
                    await self._persist(saga_id, final_state, idx, ctx)
                    raise SagaCompensationFailedError(
                        saga_id=saga_id,
                        failed_step=step.name,
                        action_error=action_exc,
                        compensation_error=compensation_exc,
                    ) from action_exc
                else:
                    final_state = SagaState.FAILED
                    await self._persist(saga_id, final_state, idx, ctx)
                    raise SagaFailedError(
                        saga_id=saga_id,
                        failed_step=step.name,
                        cause=action_exc,
                    ) from action_exc

        await self._persist(saga_id, SagaState.COMPLETED, len(self._steps), ctx)
        return ctx

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _compensate(
        self,
        saga_id: str,
        ctx: SagaContext,
        completed: list[int],
    ) -> Exception | None:
        """Run compensations in reverse; return first exception or None."""
        first_error: Exception | None = None
        for idx in reversed(completed):
            step = self._steps[idx]
            try:
                await step.compensate(ctx)
            except Exception as exc:  # noqa: BLE001
                if first_error is None:
                    first_error = exc
        return first_error

    async def _persist(
        self,
        saga_id: str,
        state: SagaState,
        step_index: int,
        ctx: SagaContext,
    ) -> None:
        if self._store is not None:
            await self._store.save(saga_id, state, step_index, ctx.snapshot())


# ---------------------------------------------------------------------------
# Saga-specific exceptions
# ---------------------------------------------------------------------------


class SagaError(Exception):
    """Base class for saga execution errors."""

    def __init__(self, saga_id: str, failed_step: str) -> None:
        self.saga_id = saga_id
        self.failed_step = failed_step
        super().__init__(f"Saga '{saga_id}' failed at step '{failed_step}'")


class SagaFailedError(SagaError):
    """Raised when a step fails but all compensations complete successfully."""

    def __init__(self, saga_id: str, failed_step: str, cause: Exception) -> None:
        super().__init__(saga_id, failed_step)
        self.cause = cause


class SagaCompensationFailedError(SagaError):
    """Raised when both a step and at least one compensation step fail."""

    def __init__(
        self,
        saga_id: str,
        failed_step: str,
        action_error: Exception,
        compensation_error: Exception,
    ) -> None:
        super().__init__(saga_id, failed_step)
        self.action_error = action_error
        self.compensation_error = compensation_error


__all__ = [
    "SagaCompensationFailedError",
    "SagaError",
    "SagaFailedError",
    "SagaOrchestrator",
]
