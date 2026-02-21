"""Unit tests for the middleware Pipeline — §10."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.application.pipeline import (
    AuthzMiddleware,
    CachingMiddleware,
    CorrelationMiddleware,
    DeduplicationMiddleware,
    IdempotencyMiddleware,
    LoggingMiddleware,
    MetricsMiddleware,
    Middleware,
    Pipeline,
    RetryMiddleware,
    TimeoutMiddleware,
    TracingMiddleware,
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


# ---------------------------------------------------------------------------
# Spy helpers shared by metric / idempotency / cache / dedup tests
# ---------------------------------------------------------------------------


class _SpyCounter:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict | None]] = []

    def add(self, value: float = 1.0, labels: dict | None = None) -> None:
        self.calls.append((value, labels))


class _SpyHistogram:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict | None]] = []

    def record(self, value: float, labels: dict | None = None) -> None:
        self.calls.append((value, labels))


class _SpyMetrics:
    """Spy Metrics port that captures all counter / histogram calls."""

    def __init__(self) -> None:
        self.counters: dict[str, _SpyCounter] = {}
        self.histograms: dict[str, _SpyHistogram] = {}

    def counter(self, name: str, description: str = "", unit: str = "") -> _SpyCounter:
        c = _SpyCounter()
        self.counters[name] = c
        return c

    def histogram(self, name: str, description: str = "", unit: str = "ms", boundaries: list | None = None) -> _SpyHistogram:
        h = _SpyHistogram()
        self.histograms[name] = h
        return h

    def gauge(self, name: str, description: str = "", unit: str = "") -> object:
        from mp_commons.observability.metrics.noop import NoopMetrics
        return NoopMetrics().gauge(name)


class _InMemIdempotencyStore:
    """Minimal in-memory IdempotencyStore for tests."""

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    async def get(self, key: object) -> object | None:
        return self._store.get(str(key))

    async def save(self, key: object, record: object) -> None:
        self._store[str(key)] = record

    async def complete(self, key: object, response: bytes) -> None:
        from mp_commons.kernel.messaging import IdempotencyRecord
        rec = self._store.get(str(key))
        if isinstance(rec, IdempotencyRecord):
            rec.status = "COMPLETED"
            rec.response = response  # type: ignore[assignment]


class _InMemCache:
    """Minimal in-memory async cache for CachingMiddleware tests."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, int]] = []

    async def get(self, key: str) -> bytes | None:
        self.get_calls.append(key)
        return self._store.get(key)

    async def set(self, key: str, value: bytes, ttl: int = 300) -> None:
        self.set_calls.append((key, ttl))
        self._store[key] = value


# ---------------------------------------------------------------------------
# LoggingMiddleware (10.3)
# ---------------------------------------------------------------------------


class TestLoggingMiddleware:
    def test_passes_through_result(self) -> None:
        result = asyncio.run(
            Pipeline().add(LoggingMiddleware()).execute("hello", identity_handler)
        )
        assert result == "hello"

    def test_propagates_exception(self) -> None:
        async def failing(req: object) -> object:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            asyncio.run(Pipeline().add(LoggingMiddleware()).execute("x", failing))


# ---------------------------------------------------------------------------
# RetryMiddleware (10.5)
# ---------------------------------------------------------------------------


class TestRetryMiddleware:
    def test_succeeds_on_first_attempt(self) -> None:
        result = asyncio.run(
            Pipeline().add(RetryMiddleware(max_attempts=3)).execute("ok", identity_handler)
        )
        assert result == "ok"

    def test_retries_and_succeeds(self) -> None:
        attempts: list[int] = []

        async def flaky(req: object) -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise OSError("transient")
            return "done"

        result = asyncio.run(
            Pipeline().add(RetryMiddleware(max_attempts=5)).execute("x", flaky)
        )
        assert result == "done"
        assert len(attempts) == 3

    def test_exhausts_attempts_raises_original(self) -> None:
        async def always_fail(req: object) -> object:
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            asyncio.run(
                Pipeline().add(RetryMiddleware(max_attempts=2)).execute("x", always_fail)
            )


# ---------------------------------------------------------------------------
# AuthzMiddleware (10.6)
# ---------------------------------------------------------------------------


def _make_principal() -> object:
    from mp_commons.kernel.security.principal import Principal
    return Principal(subject="user-1", tenant_id="tenant-1")


def _allow_engine() -> object:
    from mp_commons.kernel.security.policy import PolicyDecision

    class _Engine:
        async def evaluate(self, ctx: object) -> object:
            return PolicyDecision.ALLOW

    return _Engine()


def _deny_engine() -> object:
    from mp_commons.kernel.security.policy import PolicyDecision

    class _Engine:
        async def evaluate(self, ctx: object) -> object:
            return PolicyDecision.DENY

    return _Engine()


class TestAuthzMiddleware:
    def test_allow_passes_through(self) -> None:
        from mp_commons.kernel.security.security_context import SecurityContext

        SecurityContext.set_current(_make_principal())  # type: ignore[arg-type]
        try:
            result = asyncio.run(
                Pipeline().add(AuthzMiddleware(_allow_engine())).execute("x", identity_handler)
            )
            assert result == "x"
        finally:
            SecurityContext.clear()

    def test_deny_raises_forbidden(self) -> None:
        from mp_commons.kernel.errors import ForbiddenError
        from mp_commons.kernel.security.security_context import SecurityContext

        SecurityContext.set_current(_make_principal())  # type: ignore[arg-type]
        try:
            with pytest.raises(ForbiddenError):
                asyncio.run(
                    Pipeline().add(AuthzMiddleware(_deny_engine())).execute("x", identity_handler)
                )
        finally:
            SecurityContext.clear()

    def test_no_principal_require_auth_raises_unauthorized(self) -> None:
        from mp_commons.kernel.errors import UnauthorizedError
        from mp_commons.kernel.security.security_context import SecurityContext

        SecurityContext.clear()
        with pytest.raises(UnauthorizedError):
            asyncio.run(
                Pipeline()
                .add(AuthzMiddleware(_allow_engine(), require_auth=True))
                .execute("x", identity_handler)
            )

    def test_no_principal_passes_when_not_required(self) -> None:
        from mp_commons.kernel.security.security_context import SecurityContext

        SecurityContext.clear()
        result = asyncio.run(
            Pipeline()
            .add(AuthzMiddleware(_allow_engine(), require_auth=False))
            .execute("x", identity_handler)
        )
        assert result == "x"


# ---------------------------------------------------------------------------
# MetricsMiddleware (10.8)
# ---------------------------------------------------------------------------


class TestMetricsMiddleware:
    def test_records_call_and_latency_on_success(self) -> None:
        spy = _SpyMetrics()
        mw = MetricsMiddleware(spy)

        asyncio.run(Pipeline().add(mw).execute("ok", identity_handler))

        assert len(spy.counters["use_case.calls"].calls) == 1
        assert len(spy.histograms["use_case.latency_ms"].calls) == 1
        assert len(spy.counters["use_case.errors"].calls) == 0

    def test_records_error_counter_on_exception(self) -> None:
        spy = _SpyMetrics()
        mw = MetricsMiddleware(spy)

        async def boom(req: object) -> object:
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            asyncio.run(Pipeline().add(mw).execute("x", boom))

        assert len(spy.counters["use_case.errors"].calls) == 1
        assert len(spy.counters["use_case.calls"].calls) == 0

    def test_labels_contain_use_case_name(self) -> None:
        spy = _SpyMetrics()
        mw = MetricsMiddleware(spy)

        asyncio.run(Pipeline().add(mw).execute("ok", identity_handler))

        _, labels = spy.counters["use_case.calls"].calls[0]
        assert labels is not None
        assert labels.get("use_case") == "str"  # type(str()) == str


# ---------------------------------------------------------------------------
# TracingMiddleware (10.9)
# ---------------------------------------------------------------------------


class TestTracingMiddleware:
    def test_span_opened_and_status_ok_on_success(self) -> None:
        from mp_commons.observability.tracing.noop import NoopTracer

        result = asyncio.run(
            Pipeline().add(TracingMiddleware(NoopTracer())).execute("x", identity_handler)
        )
        assert result == "x"

    def test_span_records_exception_and_reraises(self) -> None:
        from mp_commons.observability.tracing.noop import NoopTracer
        recorded: list[Exception] = []

        class _RecordingSpan:
            def set_attribute(self, k: str, v: object) -> None:
                pass

            def set_status_ok(self) -> None:
                pass

            def record_exception(self, exc: Exception) -> None:
                recorded.append(exc)

            def end(self) -> None:
                pass

        import contextlib
        from mp_commons.observability.tracing.ports import SpanKind

        class _Tracer(NoopTracer):
            @contextlib.asynccontextmanager  # type: ignore[override]
            async def start_async_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL, attributes: dict | None = None):  # type: ignore[override]
                yield _RecordingSpan()

        async def fail(req: object) -> object:
            raise ValueError("trace-this")

        with pytest.raises(ValueError):
            asyncio.run(Pipeline().add(TracingMiddleware(_Tracer())).execute("x", fail))
        assert len(recorded) == 1
        assert isinstance(recorded[0], ValueError)


# ---------------------------------------------------------------------------
# TimeoutMiddleware (10.10)
# ---------------------------------------------------------------------------


class TestTimeoutMiddleware:
    def test_fast_call_completes(self) -> None:
        result = asyncio.run(
            Pipeline().add(TimeoutMiddleware(timeout_seconds=5.0)).execute("x", identity_handler)
        )
        assert result == "x"

    def test_slow_call_raises_app_timeout(self) -> None:
        import asyncio as _aio
        from mp_commons.kernel.errors import TimeoutError as AppTimeoutError

        async def slow(req: object) -> object:
            await _aio.sleep(10)
            return req

        with pytest.raises(AppTimeoutError):
            asyncio.run(
                Pipeline().add(TimeoutMiddleware(timeout_seconds=0.001)).execute("x", slow)
            )


# ---------------------------------------------------------------------------
# IdempotencyMiddleware (10.11)
# ---------------------------------------------------------------------------


class _ReqWithKey:
    def __init__(self, key: str) -> None:
        self.idempotency_key = key


class _ReqNoKey:
    pass


class TestIdempotencyMiddleware:
    def test_no_idempotency_key_passes_through(self) -> None:
        store = _InMemIdempotencyStore()
        result = asyncio.run(
            Pipeline().add(IdempotencyMiddleware(store)).execute(_ReqNoKey(), identity_handler)
        )
        assert isinstance(result, _ReqNoKey)

    def test_new_key_saves_and_completes_record(self) -> None:
        from mp_commons.kernel.messaging import IdempotencyRecord
        store = _InMemIdempotencyStore()
        handled: list[object] = []

        async def capturing(req: object) -> str:
            handled.append(req)
            return "result-123"

        asyncio.run(
            Pipeline().add(IdempotencyMiddleware(store)).execute(_ReqWithKey("k1"), capturing)
        )
        assert len(handled) == 1
        # Record should be COMPLETED after successful execution
        key = "_ReqWithKey:k1"
        rec = store._store.get(key)
        assert isinstance(rec, IdempotencyRecord)
        assert rec.status == "COMPLETED"

    def test_completed_record_returns_cached_without_calling_handler(self) -> None:
        from mp_commons.kernel.messaging import IdempotencyKey, IdempotencyRecord
        store = _InMemIdempotencyStore()
        ikey = IdempotencyKey(client_key="k2", operation="_ReqWithKey")
        rec = IdempotencyRecord(key=str(ikey), status="COMPLETED", response=b"cached-response")  # type: ignore[arg-type]
        store._store[str(ikey)] = rec

        called: list[bool] = []

        async def should_not_be_called(req: object) -> object:
            called.append(True)
            return "should-not-reach"

        result = asyncio.run(
            Pipeline().add(IdempotencyMiddleware(store)).execute(_ReqWithKey("k2"), should_not_be_called)
        )
        assert result == b"cached-response"
        assert called == []

    def test_second_call_same_key_returns_cached(self) -> None:
        store = _InMemIdempotencyStore()
        calls: list[int] = []

        async def counting(req: object) -> str:
            calls.append(1)
            return "value"

        async def _run() -> tuple[object, object]:
            r1 = await Pipeline().add(IdempotencyMiddleware(store)).execute(_ReqWithKey("k3"), counting)
            r2 = await Pipeline().add(IdempotencyMiddleware(store)).execute(_ReqWithKey("k3"), counting)
            return r1, r2

        r1, r2 = asyncio.run(_run())
        assert r1 == "value"
        # Second call returns cached bytes representation (completed record)
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# CachingMiddleware (10.13)
# ---------------------------------------------------------------------------


class TestCachingMiddleware:
    def test_command_bypasses_cache(self) -> None:
        from mp_commons.application.cqrs import Command

        class MyCmd(Command):
            pass

        cache = _InMemCache()
        calls: list[int] = []

        async def counting(req: object) -> str:
            calls.append(1)
            return "cmd-result"

        asyncio.run(Pipeline().add(CachingMiddleware(cache)).execute(MyCmd(), counting))
        asyncio.run(Pipeline().add(CachingMiddleware(cache)).execute(MyCmd(), counting))

        assert len(calls) == 2
        assert cache.set_calls == []  # cache never written for commands

    def test_query_cached_on_second_call(self) -> None:
        from mp_commons.application.cqrs import Query

        class GetWidget(Query):
            def __init__(self, widget_id: str) -> None:
                self.widget_id = widget_id

        cache = _InMemCache()
        calls: list[int] = []

        async def handler(req: object) -> str:
            calls.append(1)
            return "widget-data"

        async def _run() -> tuple[object, object]:
            mw = CachingMiddleware(cache)
            r1 = await Pipeline().add(mw).execute(GetWidget("w1"), handler)
            r2 = await Pipeline().add(mw).execute(GetWidget("w1"), handler)
            return r1, r2

        r1, r2 = asyncio.run(_run())
        assert r1 == "widget-data"
        assert r2 == "widget-data"
        assert len(calls) == 1  # handler only called once

    def test_different_query_instances_different_cache_keys(self) -> None:
        from mp_commons.application.cqrs import Query

        class GetWidget(Query):
            def __init__(self, widget_id: str) -> None:
                self.widget_id = widget_id

        cache = _InMemCache()
        calls: list[str] = []

        async def handler(req: object) -> str:
            wid = getattr(req, "widget_id", "?")
            calls.append(wid)
            return f"widget-{wid}"

        async def _run() -> tuple[object, object]:
            mw = CachingMiddleware(cache)
            r1 = await Pipeline().add(mw).execute(GetWidget("w1"), handler)
            r2 = await Pipeline().add(mw).execute(GetWidget("w2"), handler)
            return r1, r2

        r1, r2 = asyncio.run(_run())
        assert r1 == "widget-w1"
        assert r2 == "widget-w2"
        assert len(calls) == 2


# ---------------------------------------------------------------------------
# DeduplicationMiddleware (10.14)
# ---------------------------------------------------------------------------


class _CmdWithId:
    def __init__(self, command_id: str) -> None:
        self.command_id = command_id


class _CmdNoId:
    pass


class TestDeduplicationMiddleware:
    def test_command_without_id_passes_through(self) -> None:
        from mp_commons.application.cqrs import Command

        class NoIdCmd(Command):
            pass

        store = _InMemIdempotencyStore()
        calls: list[int] = []

        async def counting(req: object) -> str:
            calls.append(1)
            return "ok"

        asyncio.run(
            Pipeline().add(DeduplicationMiddleware(store)).execute(NoIdCmd(), counting)
        )
        asyncio.run(
            Pipeline().add(DeduplicationMiddleware(store)).execute(NoIdCmd(), counting)
        )
        assert len(calls) == 2  # no dedup without id

    def test_new_command_id_executes_handler(self) -> None:
        from mp_commons.application.cqrs import Command

        class MyCmd(Command):
            def __init__(self, command_id: str) -> None:
                self.command_id = command_id

        store = _InMemIdempotencyStore()
        calls: list[int] = []

        async def counting(req: object) -> str:
            calls.append(1)
            return "ok"

        asyncio.run(
            Pipeline().add(DeduplicationMiddleware(store)).execute(MyCmd("c1"), counting)
        )
        assert calls == [1]

    def test_completed_command_returns_cached_without_calling_handler(self) -> None:
        from mp_commons.application.cqrs import Command
        from mp_commons.kernel.messaging import IdempotencyKey, IdempotencyRecord

        class MyCmd(Command):
            def __init__(self, command_id: str) -> None:
                self.command_id = command_id

        store = _InMemIdempotencyStore()
        ikey = IdempotencyKey(client_key="c2", operation="MyCmd")
        store._store[str(ikey)] = IdempotencyRecord(
            key=str(ikey), status="COMPLETED", response=b"cached"  # type: ignore[arg-type]
        )

        called: list[bool] = []

        async def blocked(req: object) -> object:
            called.append(True)
            return "unreachable"

        result = asyncio.run(
            Pipeline().add(DeduplicationMiddleware(store)).execute(MyCmd("c2"), blocked)
        )
        assert result == b"cached"
        assert called == []

    def test_processing_command_raises_conflict(self) -> None:
        from mp_commons.application.cqrs import Command
        from mp_commons.kernel.errors import ConflictError
        from mp_commons.kernel.messaging import IdempotencyKey, IdempotencyRecord

        class MyCmd(Command):
            def __init__(self, command_id: str) -> None:
                self.command_id = command_id

        store = _InMemIdempotencyStore()
        ikey = IdempotencyKey(client_key="c3", operation="MyCmd")
        store._store[str(ikey)] = IdempotencyRecord(key=str(ikey), status="PROCESSING")

        with pytest.raises(ConflictError, match="Duplicate command"):
            asyncio.run(
                Pipeline().add(DeduplicationMiddleware(store)).execute(MyCmd("c3"), identity_handler)
            )
