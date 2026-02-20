"""Application saga – SagaStep abstract base class."""

from __future__ import annotations

import abc

from mp_commons.application.saga.context import SagaContext


class SagaStep(abc.ABC):
    """A single unit of work within a saga.

    Subclass and implement :meth:`action` (the forward step) and
    :meth:`compensate` (the rollback step invoked on failure).
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable name used for logging and store records."""

    @abc.abstractmethod
    async def action(self, ctx: SagaContext) -> None:
        """Execute the forward step.  Write results into *ctx*.

        Raise any exception to signal failure.
        """

    @abc.abstractmethod
    async def compensate(self, ctx: SagaContext) -> None:
        """Undo the effects of :meth:`action`.

        Called during the compensation phase when a later step fails.
        Raise any exception to signal a compensation failure.
        """

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"


__all__ = ["SagaStep"]
