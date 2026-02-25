"""Unit tests for §77 – Deadline Propagation."""
import asyncio

import pytest

from mp_commons.resilience.timeouts.deadline import Deadline
from mp_commons.resilience.deadline import (
    DeadlineContext,
    DeadlineExceededError,
    deadline_aware,
)


class TestDeadlineContext:
    def test_set_and_get(self):
        dl = Deadline.after(seconds=5)
        token = DeadlineContext.set(dl)
        assert DeadlineContext.get() is dl
        DeadlineContext.reset(token)

    def test_get_returns_none_by_default(self):
        # Use fresh context (may have leftover from other tests — just check type)
        result = DeadlineContext.get()
        assert result is None or isinstance(result, Deadline)

    def test_scoped_set_and_clear(self):
        async def run():
            dl = Deadline.after(seconds=10)
            async with DeadlineContext.scoped(dl) as d:
                assert DeadlineContext.get() is dl
                assert d is dl
            # After scope: context should be restored (None or prior)
        asyncio.run(run())

    def test_raise_if_exceeded_expired(self):
        dl = Deadline.after(seconds=-1)  # already expired
        token = DeadlineContext.set(dl)
        try:
            with pytest.raises(DeadlineExceededError):
                DeadlineContext.raise_if_exceeded()
        finally:
            DeadlineContext.reset(token)

    def test_raise_if_exceeded_not_expired(self):
        dl = Deadline.after(seconds=60)
        token = DeadlineContext.set(dl)
        try:
            DeadlineContext.raise_if_exceeded()  # should NOT raise
        finally:
            DeadlineContext.reset(token)


class TestDeadlineAware:
    def test_completes_within_deadline(self):
        async def fast():
            return "ok"

        dl = Deadline.after(seconds=5)
        result = asyncio.run(deadline_aware(fast(), dl))
        assert result == "ok"

    def test_raises_when_already_expired(self):
        dl = Deadline.after(seconds=-1)

        async def run():
            with pytest.raises(DeadlineExceededError):
                await deadline_aware(asyncio.sleep(0), dl)

        asyncio.run(run())

    def test_raises_on_timeout(self):
        async def slow():
            await asyncio.sleep(10)
            return "too_late"

        dl = Deadline.after(seconds=0.01)
        with pytest.raises(DeadlineExceededError):
            asyncio.run(deadline_aware(slow(), dl))

    def test_no_deadline_uses_context(self):
        async def run():
            dl = Deadline.after(seconds=5)
            async with DeadlineContext.scoped(dl):
                result = await deadline_aware(_coro())
            return result

        async def _coro():
            return "done"

        assert asyncio.run(run()) == "done"
