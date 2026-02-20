"""Unit tests for the middleware Pipeline."""

from __future__ import annotations

import pytest

from mp_commons.application.pipeline import Middleware, Pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_recording_middleware(name: str, record: list[str]) -> Middleware:
    """Middleware that appends *name* before and after calling next."""

    class Rec(Middleware):
        async def __call__(self, request: object, next_: object) -> object:  # type: ignore[override]
            record.append(f"{name}:before")
            result = await next_(request)  # type: ignore[operator]
            record.append(f"{name}:after")
            return result

    return Rec()


async def identity_handler(request: object) -> object:
    return request


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPipeline:
    @pytest.mark.asyncio
    async def test_no_middleware_calls_handler(self) -> None:
        pipeline = Pipeline()
        result = await pipeline.execute("hello", identity_handler)
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_single_middleware_wraps(self) -> None:
        record: list[str] = []
        pipeline = Pipeline()
        pipeline.add(make_recording_middleware("A", record))

        result = await pipeline.execute("x", identity_handler)
        assert result == "x"
        assert record == ["A:before", "A:after"]

    @pytest.mark.asyncio
    async def test_middleware_ordering_inside_out(self) -> None:
        """Middleware added first should be outermost (first before, last after)."""
        record: list[str] = []
        pipeline = Pipeline()
        pipeline.add(make_recording_middleware("A", record))
        pipeline.add(make_recording_middleware("B", record))

        await pipeline.execute("x", identity_handler)
        assert record == ["A:before", "B:before", "B:after", "A:after"]

    @pytest.mark.asyncio
    async def test_fluent_add_returns_pipeline(self) -> None:
        record: list[str] = []
        pipeline = (
            Pipeline()
            .add(make_recording_middleware("A", record))
            .add(make_recording_middleware("B", record))
        )
        await pipeline.execute("x", identity_handler)
        assert record == ["A:before", "B:before", "B:after", "A:after"]

    @pytest.mark.asyncio
    async def test_short_circuit_in_middleware(self) -> None:
        """Middleware that does not call next should still work."""

        class ShortCircuit(Middleware):
            async def __call__(self, request: object, next_: object) -> str:  # type: ignore[override]
                return "short-circuited"

        pipeline = Pipeline().add(ShortCircuit())
        result = await pipeline.execute("ignored", identity_handler)
        assert result == "short-circuited"
