"""conftest.py for benchmarks.

Provides a reusable event loop and shared fixtures for async benchmarks.

The ``event_loop`` fixture is session-scoped so every benchmark in the
session shares a single asyncio event loop — this amortises the
``asyncio.new_event_loop()`` startup cost and gives more stable timing.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop shared by all async benchmark helpers."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def run_async(event_loop):
    """Helper that executes a coroutine in the session event loop.

    Usage inside a benchmark::

        def test_something(benchmark, run_async):
            benchmark(run_async, some_coroutine_factory())
    """

    def _run(coro):
        return event_loop.run_until_complete(coro)

    return _run
