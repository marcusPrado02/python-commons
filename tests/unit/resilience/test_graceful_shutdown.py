"""Unit tests for GracefulShutdown (R-02)."""

from __future__ import annotations

import asyncio

from mp_commons.resilience.graceful_shutdown import GracefulShutdown


class TestGracefulShutdown:
    def test_initial_state(self):
        s = GracefulShutdown()
        assert not s.is_shutting_down
        assert s.triggered_by is None
        assert s.hook_count == 0

    def test_register_hook(self):
        s = GracefulShutdown()
        s.register(lambda: None)
        assert s.hook_count == 1

    def test_on_shutdown_decorator(self):
        s = GracefulShutdown()

        @s.on_shutdown
        def my_hook():
            pass

        assert s.hook_count == 1
        assert my_hook is my_hook  # decorator returns the original function

    async def test_run_hooks_lifo_order(self):
        s = GracefulShutdown()
        order: list[int] = []
        s.register(lambda: order.append(1))
        s.register(lambda: order.append(2))
        s.register(lambda: order.append(3))
        await s.run_hooks()
        assert order == [3, 2, 1]  # LIFO

    async def test_run_async_hooks(self):
        s = GracefulShutdown()
        ran: list[str] = []

        async def async_hook():
            await asyncio.sleep(0)
            ran.append("async")

        s.register(async_hook)
        await s.run_hooks()
        assert ran == ["async"]

    async def test_programmatic_trigger_and_wait(self):
        s = GracefulShutdown()
        ran: list[str] = []
        s.register(lambda: ran.append("hook"))

        async def trigger_soon():
            await asyncio.sleep(0.01)
            s.trigger()

        asyncio.create_task(trigger_soon())
        await s.wait()

        assert s.is_shutting_down
        assert ran == ["hook"]

    async def test_hook_exception_does_not_stop_other_hooks(self):
        s = GracefulShutdown()
        ran: list[int] = []

        def bad_hook():
            raise RuntimeError("explode")

        s.register(lambda: ran.append(1))
        s.register(bad_hook)
        s.register(lambda: ran.append(3))

        await s.run_hooks()
        # hooks 3 and 1 run despite bad_hook failing (LIFO: 3 → bad → 1)
        assert 3 in ran
        assert 1 in ran

    async def test_drain_timeout_skips_remaining_hooks(self):
        s = GracefulShutdown(drain_timeout=0.05)
        ran: list[int] = []

        async def slow_hook():
            await asyncio.sleep(1.0)
            ran.append(99)

        s.register(lambda: ran.append(1))
        s.register(slow_hook)  # registered second → called first (LIFO)

        await s.run_hooks()
        # slow_hook times out; hook appending 1 is skipped due to budget exhausted
        assert 99 not in ran

    def test_trigger_sets_is_shutting_down(self):
        s = GracefulShutdown()
        assert not s.is_shutting_down
        s.trigger()
        assert s.is_shutting_down

    def test_double_trigger_is_idempotent(self):
        s = GracefulShutdown()
        s.trigger()
        s.trigger()  # should not raise
        assert s.is_shutting_down

    async def test_run_hooks_when_empty_is_safe(self):
        s = GracefulShutdown()
        await s.run_hooks()  # must not raise
