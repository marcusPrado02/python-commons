"""Unit tests for the middleware Pipeline — §10."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.application.pipeline import (
    CorrelationMiddleware,
    Middleware,
    Pipeline,
    ValidationMiddleware,
)
from mp_commons.kernel.errors import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_recording_middleware(name: str, record: list[str]) -> Middleware:
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
# Pipeline (10.1–10.2)
# ---------------------------------------------------------------------------


class TestPipeline:
    def test_no_middleware_calls_handler(self) -> None:
        result = asyncio.run(Pipeline().execute("hello", identity_handler))
        assert result == "hello"

    def test_single_middleware_wraps(self) -> None:
        record: list[str] = []
        pipeline = Pipeline()
        pipeline.add(make_recording_middleware("A", record))

        result = asyncio.run(pipeline.execute("x", identity_handler))
        assert result == "x"
        assert record == ["A:before", "A:after"]

    def test_middleware_ordering_inside_out(self) -> None:
        record: list[str] = []
        pipeline = Pipeline()
        pipeline.add(make_recording_middleware("A", record))
        pipeline.add(make_recording_middleware("B", record))

        asyncio.run(pipeline.execute("x", identity_handler))
        assert record == ["A:before", "B:before", "B:after", "A:after"]

    def test_fluent_add_returns_pipeline(self) -> None:
        record: list[str] = []
        pipeline = (
            Pipeline()
            .add(make_recording_middleware("A", record))
            .add(make_recording_middleware("B", record))
        )
        asyncio.run(pipeline.execute("x", identity_handler))
        assert record == ["A:before", "B:before", "B:after", "A:after"]

    def test_short_circuit_in_middleware(self) -> None:
        class ShortCircuit(Middleware):
            async def __call__(self, request: object, next_: object) -> str:  # type: ignore[override]
                return "short-circuited"

        pipeline = Pipeline().add(ShortCircuit())
        result = asyncio.run(pipeline.execute("ignored", identity_handler))
        assert result == "short-circuited"

    def test_multiple_requests_independent(self) -> None:
        results: list[str] = []

        async def capturing_handler(req: object) -> object:
            results.append(str(req))
            return req

        async def _run() -> None:
            p = Pipeline()
            await p.execute("a", capturing_handler)
            await p.execute("b", capturing_handler)

        asyncio.run(_run())
        assert results == ["a", "b"]


# ---------------------------------------------------------------------------
# ValidationMiddleware (10.4)
# ---------------------------------------------------------------------------


class TestValidationMiddleware:
    def test_calls_validate_if_present(self) -> None:
        validated: list[bool] = []

        class MyRequest:
            def validate(self) -> None:
                validated.append(True)

        pipeline = Pipeline().add(ValidationMiddleware())
        asyncio.run(pipeline.execute(MyRequest(), identity_handler))
        assert validated == [True]

    def test_no_validate_method_passes_through(self) -> None:
        class NoValidate:
            pass

        result = asyncio.run(
            Pipeline().add(ValidationMiddleware()).execute(NoValidate(), identity_handler)
        )
        assert isinstance(result, NoValidate)

    def test_validate_raises_propagates(self) -> None:
        class BadRequest:
            def validate(self) -> None:
                raise ValueError("bad input")

        with pytest.raises(ValueError, match="bad input"):
            asyncio.run(
                Pipeline().add(ValidationMiddleware()).execute(BadRequest(), identity_handler)
            )


# ---------------------------------------------------------------------------
# CorrelationMiddleware (10.7)
# ---------------------------------------------------------------------------


class TestCorrelationMiddleware:
    def test_sets_correlation_id_when_absent(self) -> None:
        captured: list[str] = []

        class Req:
            correlation_id: str | None = None

        req = Req()

        async def capturing(r: object) -> object:
            captured.append(getattr(r, "correlation_id", None))
            return r

        asyncio.run(Pipeline().add(CorrelationMiddleware()).execute(req, capturing))
        assert len(captured) == 1
        assert captured[0] is not None
        assert len(captured[0]) > 0

    def test_does_not_overwrite_existing_correlation_id(self) -> None:
        captured: list[str] = []

        class Req:
            correlation_id = "existing-corr-id"

        req = Req()

        async def capturing(r: object) -> object:
            captured.append(getattr(r, "correlation_id", None))
            return r

        asyncio.run(Pipeline().add(CorrelationMiddleware()).execute(req, capturing))
        assert captured[0] == "existing-corr-id"


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.application.pipeline")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing"
