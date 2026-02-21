"""§47.2 — Benchmark: InProcessCommandBus.dispatch.

Measures the median dispatch latency of:
- A bare InProcessCommandBus with no pipeline
- A 5-noop-middleware Pipeline wrapping the bus dispatch

Target: sustain ≥10 000 dispatches/s (median < 100 µs per dispatch).
"""

from __future__ import annotations

import asyncio
from typing import Any

from mp_commons.application.cqrs.commands import (
    Command,
    CommandHandler,
    InProcessCommandBus,
)
from mp_commons.application.pipeline.middleware import Middleware, Next
from mp_commons.application.pipeline.pipeline import Pipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _PlaceOrder(Command):
    """Minimal command used only in benchmarks."""


class _PlaceOrderHandler(CommandHandler["_PlaceOrder"]):
    async def handle(self, command: "_PlaceOrder") -> str:
        return "ok"


class _NoOpMiddleware(Middleware):
    """Zero-overhead pass-through middleware."""

    async def __call__(self, request: Any, next_: Next) -> Any:
        return await next_(request)


def _make_bus() -> InProcessCommandBus:
    bus = InProcessCommandBus()
    bus.register(_PlaceOrder, _PlaceOrderHandler())
    return bus


def _make_pipeline(middlewares: int = 5) -> Pipeline:
    pipeline = Pipeline()
    for _ in range(middlewares):
        pipeline.add(_NoOpMiddleware())
    return pipeline


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


def test_bus_dispatch_bare(benchmark, event_loop):
    """Bare InProcessCommandBus.dispatch (no middleware)."""
    bus = _make_bus()
    cmd = _PlaceOrder()

    def run():
        return event_loop.run_until_complete(bus.dispatch(cmd))

    result = benchmark(run)
    assert result == "ok"


def test_bus_dispatch_5_middleware_pipeline(benchmark, event_loop):
    """InProcessCommandBus through a 5-level noop Pipeline."""
    bus = _make_bus()
    pipeline = _make_pipeline(5)
    cmd = _PlaceOrder()

    def run():
        return event_loop.run_until_complete(
            pipeline.execute(cmd, bus.dispatch)
        )

    result = benchmark(run)
    assert result == "ok"


def test_bus_dispatch_pipeline_overhead(benchmark, event_loop):
    """Compare 1-layer vs 5-layer pipeline to isolate per-layer cost."""
    bus = _make_bus()
    pipeline = _make_pipeline(1)
    cmd = _PlaceOrder()

    def run():
        return event_loop.run_until_complete(
            pipeline.execute(cmd, bus.dispatch)
        )

    result = benchmark(run)
    assert result == "ok"
