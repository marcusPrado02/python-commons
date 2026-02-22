"""Testing generators – StepClock (§38.4)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta


class StepClock:
    """A deterministic clock that advances by a fixed delta on every
    :meth:`now` call.

    Useful for testing time-ordered sequences where each operation must
    produce a strictly increasing timestamp without relying on wall time.

    Parameters
    ----------
    start:
        The datetime returned on the *first* :meth:`now` call.
        Defaults to ``2026-01-01 00:00:00 UTC``.
    step:
        Amount to advance after each :meth:`now` call.  Accepts any keyword
        argument accepted by :class:`datetime.timedelta` (e.g.
        ``seconds=1``, ``minutes=5``, ``milliseconds=100``).

    Example::

        clock = StepClock(step=timedelta(seconds=1))
        t0 = clock.now()   # 2026-01-01 00:00:00
        t1 = clock.now()   # 2026-01-01 00:00:01
        t2 = clock.now()   # 2026-01-01 00:00:02
    """

    def __init__(
        self,
        start: datetime | None = None,
        step: timedelta | None = None,
        **step_kwargs: int | float,
    ) -> None:
        self._current = start or datetime(2026, 1, 1, tzinfo=UTC)
        if step is not None:
            self._step = step
        elif step_kwargs:
            self._step = timedelta(**step_kwargs)
        else:
            self._step = timedelta(seconds=1)
        self._call_count = 0

    # ------------------------------------------------------------------
    # Clock protocol
    # ------------------------------------------------------------------

    def now(self) -> datetime:
        """Return the current tick and advance the clock by one step."""
        value = self._current
        self._current += self._step
        self._call_count += 1
        return value

    def today(self):  # type: ignore[return]  # returns date
        return self.now().date()

    def timestamp(self) -> float:
        return self.now().timestamp()

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def call_count(self) -> int:
        """Number of :meth:`now` / :meth:`today` / :meth:`timestamp` calls."""
        return self._call_count

    def reset(self, start: datetime | None = None) -> None:
        """Reset the clock to *start* (or original start) and clear the
        call counter."""
        if start is not None:
            self._current = start
        else:
            self._current = datetime(2026, 1, 1, tzinfo=UTC)
        self._call_count = 0

    def peek(self) -> datetime:
        """Return the next value :meth:`now` would return without advancing."""
        return self._current


__all__ = ["StepClock"]
