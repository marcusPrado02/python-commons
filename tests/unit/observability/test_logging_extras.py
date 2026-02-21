"""Unit tests for §16.4, §15.6, §20.3, §20.5, §20.7, §20.8, §20.9."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import MagicMock, call

import pytest


# ---------------------------------------------------------------------------
# §16.4  CircuitOpenError
# ---------------------------------------------------------------------------

class TestCircuitOpenError:
    """§16.4 – CircuitOpenError is an InfrastructureError."""

    def test_is_infrastructure_error(self) -> None:
        from mp_commons.kernel.errors import InfrastructureError
        from mp_commons.resilience.circuit_breaker import CircuitOpenError

        err = CircuitOpenError("my-circuit")
        assert isinstance(err, InfrastructureError)

    def test_stores_circuit_name(self) -> None:
        from mp_commons.resilience.circuit_breaker import CircuitOpenError

        err = CircuitOpenError("svc-downstream")
        assert err.circuit_name == "svc-downstream"

    def test_default_message_includes_circuit_name(self) -> None:
        from mp_commons.resilience.circuit_breaker import CircuitOpenError

        err = CircuitOpenError("auth-service")
        assert "auth-service" in str(err)

    def test_custom_message(self) -> None:
        from mp_commons.resilience.circuit_breaker import CircuitOpenError

        err = CircuitOpenError("x", "custom message")
        assert err.to_dict()["message"] == "custom message"

    def test_to_dict_includes_circuit_name(self) -> None:
        from mp_commons.resilience.circuit_breaker import CircuitOpenError

        d = CircuitOpenError("my-cb").to_dict()
        assert d["circuit_name"] == "my-cb"
        assert "code" in d
        assert "message" in d

    def test_circuit_breaker_raises_circuit_open_error(self) -> None:
        from mp_commons.resilience.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerPolicy,
            CircuitBreakerState,
            CircuitOpenError,
        )

        cb = CircuitBreaker(
            "my-service",
            CircuitBreakerPolicy(failure_threshold=1, timeout_seconds=999),
        )

        async def run() -> None:
            # Trip the breaker
            with pytest.raises(ValueError):
                await cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
            assert cb.state == CircuitBreakerState.OPEN

            # Next call must raise CircuitOpenError
            with pytest.raises(CircuitOpenError) as exc_info:
                await cb.call(lambda: asyncio.sleep(0))
            assert exc_info.value.circuit_name == "my-service"

        asyncio.run(run())
# ---------------------------------------------------------------------------

class TestTenacityRetryPolicy:
    """§15.6 – TenacityRetryPolicy mirrors RetryPolicy interface."""

    def test_successful_call_no_retry(self) -> None:
        from mp_commons.resilience.retry import TenacityRetryPolicy

        calls: list[int] = []

        def fn() -> str:
            calls.append(1)
            return "ok"

        policy = TenacityRetryPolicy(max_attempts=3)
        result = policy.execute(fn)
        assert result == "ok"
        assert len(calls) == 1

    def test_retries_on_failure_then_succeeds(self) -> None:
        from mp_commons.resilience.retry import TenacityRetryPolicy
        import tenacity

        calls: list[int] = []

        def fn() -> str:
            calls.append(1)
            if len(calls) < 3:
                raise IOError("transient")
            return "recovered"

        policy = TenacityRetryPolicy(
            max_attempts=3,
            wait=tenacity.wait_none(),
            retry=tenacity.retry_if_exception_type(IOError),
        )
        result = policy.execute(fn)
        assert result == "recovered"
        assert len(calls) == 3

    def test_raises_after_max_attempts(self) -> None:
        from mp_commons.resilience.retry import TenacityRetryPolicy
        import tenacity

        policy = TenacityRetryPolicy(
            max_attempts=2,
            wait=tenacity.wait_none(),
            reraise=True,
        )

        with pytest.raises(RuntimeError, match="fail"):
            policy.execute(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

    def test_execute_async_retries(self) -> None:
        from mp_commons.resilience.retry import TenacityRetryPolicy
        import tenacity

        calls: list[int] = []

        async def fn() -> str:
            calls.append(1)
            if len(calls) < 2:
                raise IOError("transient")
            return "async_ok"

        policy = TenacityRetryPolicy(
            max_attempts=3,
            wait=tenacity.wait_none(),
            retry=tenacity.retry_if_exception_type(IOError),
        )

        async def run() -> str:
            return await policy.execute_async(fn)

        result = asyncio.run(run())
        assert result == "async_ok"
        assert len(calls) == 2

    def test_missing_tenacity_raises_import_error(self) -> None:
        """TenacityRetryPolicy raises ImportError when tenacity unavailable."""
        from unittest.mock import patch
        import builtins

        real_import = builtins.__import__

        def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "tenacity":
                raise ImportError("No module named 'tenacity'")
            return real_import(name, *args, **kwargs)

        from mp_commons.resilience.retry.tenacity_adapter import TenacityRetryPolicy
        with patch("builtins.__import__", side_effect=fake_import):
            with pytest.raises(ImportError, match="tenacity"):
                TenacityRetryPolicy(max_attempts=1)


# ---------------------------------------------------------------------------
# §20.3  CorrelationProcessor
# ---------------------------------------------------------------------------

class TestCorrelationProcessor:
    """§20.3 – injects correlation context into log event dicts."""

    def test_injects_correlation_id_when_context_set(self) -> None:
        from mp_commons.observability.correlation import CorrelationContext, RequestContext
        from mp_commons.observability.logging import CorrelationProcessor

        CorrelationContext.set(RequestContext(correlation_id="test-cid", tenant_id="t1"))
        try:
            proc = CorrelationProcessor()
            event_dict: dict[str, Any] = {"event": "test"}
            result = proc(None, "info", event_dict)
            assert result["correlation_id"] == "test-cid"
            assert result["tenant_id"] == "t1"
        finally:
            CorrelationContext.clear()

    def test_does_not_overwrite_existing_correlation_id(self) -> None:
        from mp_commons.observability.correlation import CorrelationContext, RequestContext
        from mp_commons.observability.logging import CorrelationProcessor

        CorrelationContext.set(RequestContext(correlation_id="from-context"))
        try:
            proc = CorrelationProcessor()
            event_dict: dict[str, Any] = {"event": "x", "correlation_id": "already-set"}
            result = proc(None, "info", event_dict)
            assert result["correlation_id"] == "already-set"
        finally:
            CorrelationContext.clear()

    def test_no_context_passes_through(self) -> None:
        from mp_commons.observability.correlation import CorrelationContext
        from mp_commons.observability.logging import CorrelationProcessor

        CorrelationContext.clear()
        proc = CorrelationProcessor()
        event_dict: dict[str, Any] = {"event": "test"}
        result = proc(None, "info", event_dict)
        assert "correlation_id" not in result

    def test_optional_fields_injected_only_when_set(self) -> None:
        from mp_commons.observability.correlation import CorrelationContext, RequestContext
        from mp_commons.observability.logging import CorrelationProcessor

        CorrelationContext.set(RequestContext(
            correlation_id="cid",
            tenant_id=None,
            user_id="u-42",
            trace_id="t-trace",
        ))
        try:
            proc = CorrelationProcessor()
            result = proc(None, "info", {"event": "x"})
            assert "tenant_id" not in result
            assert result["user_id"] == "u-42"
            assert result["trace_id"] == "t-trace"
        finally:
            CorrelationContext.clear()


# ---------------------------------------------------------------------------
# §20.5  get_logger
# ---------------------------------------------------------------------------

class TestGetLogger:
    """§20.5 – get_logger returns a usable logger."""

    def test_returns_a_logger(self) -> None:
        from mp_commons.observability.logging import get_logger

        log = get_logger("test.module")
        assert log is not None

    def test_returned_logger_has_info_method(self) -> None:
        from mp_commons.observability.logging import get_logger

        log = get_logger("test.module")
        assert callable(getattr(log, "info", None))

    def test_kwargs_bind_context(self) -> None:
        from mp_commons.observability.logging import get_logger

        # Should not raise
        log = get_logger("test.module", service="my-svc", version="1.0")
        assert log is not None


# ---------------------------------------------------------------------------
# §20.7  AuditLogger
# ---------------------------------------------------------------------------

class TestAuditLogger:
    """§20.7 – AuditLogger emits structured audit entries."""

    def _capture_logger(self) -> tuple[Any, list[str]]:
        """Return a mock logger and a list that collects emitted messages."""
        messages: list[str] = []

        class CaptureLogger:
            def warning(self, event: Any, **kwargs: Any) -> None:
                messages.append(str(event))

        return CaptureLogger(), messages

    def test_log_access_emits_warning(self) -> None:
        from mp_commons.observability.logging import AuditLogger

        underlying, msgs = self._capture_logger()
        log = AuditLogger(service="api", logger=underlying)

        class FakePrincipal:
            id = "user-99"

        log.log_access(FakePrincipal(), resource="doc:1", action="read")
        assert len(msgs) == 1
        assert "audit.access" in msgs[0]

    def test_log_access_outcome_failure(self) -> None:
        from mp_commons.observability.logging import AuditLogger, AuditOutcome

        underlying, msgs = self._capture_logger()
        log = AuditLogger(logger=underlying)
        log.log_access("anon", resource="secret", action="delete", outcome=AuditOutcome.DENIED)
        assert msgs  # at least one entry

    def test_log_security_event(self) -> None:
        from mp_commons.observability.logging import AuditLogger

        underlying, msgs = self._capture_logger()
        log = AuditLogger(logger=underlying)
        log.log_security_event("login", description="User logged in")
        assert len(msgs) == 1
        assert "audit.login" in msgs[0]

    def test_principal_id_extracted_from_object(self) -> None:
        """Ensures principal.id is used, not str(principal)."""
        from mp_commons.observability.logging import AuditLogger

        captured: list[dict[str, Any]] = []

        class CaptureLogger:
            def warning(self, event: Any, **kwargs: Any) -> None:
                captured.append({"event": event, **kwargs})

        class FakePrincipal:
            id = "user-special-id"

        log = AuditLogger(logger=CaptureLogger())
        log.log_access(FakePrincipal(), resource="x", action="read")
        assert captured[0]["principal_id"] == "user-special-id"

    def test_default_logger_does_not_raise(self) -> None:
        from mp_commons.observability.logging import AuditLogger

        log = AuditLogger(service="test")
        log.log_access("anon", resource="r", action="read")

    def test_audit_outcome_enum_values(self) -> None:
        from mp_commons.observability.logging import AuditOutcome

        assert AuditOutcome.SUCCESS.value == "success"
        assert AuditOutcome.FAILURE.value == "failure"
        assert AuditOutcome.DENIED.value == "denied"
        assert AuditOutcome.ERROR.value == "error"


# ---------------------------------------------------------------------------
# §20.8  AsyncLogHandler
# ---------------------------------------------------------------------------

class TestAsyncLogHandler:
    """§20.8 – AsyncLogHandler enqueues records without blocking."""

    def _make_handler(self) -> tuple[Any, list[logging.LogRecord]]:
        records: list[logging.LogRecord] = []

        class CollectHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        collect = CollectHandler()
        from mp_commons.observability.logging import AsyncLogHandler

        handler = AsyncLogHandler(delegate=collect)
        return handler, records

    def test_emitted_record_eventually_delivered(self) -> None:
        handler, records = self._make_handler()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None,
        )
        handler.emit(record)
        handler.drain_sync()
        assert len(records) == 1
        assert records[0].msg == "hello"

    def test_multiple_records(self) -> None:
        handler, records = self._make_handler()
        for i in range(5):
            r = logging.LogRecord(
                name="test", level=logging.DEBUG, pathname="", lineno=0,
                msg=f"msg-{i}", args=(), exc_info=None,
            )
            handler.emit(r)
        handler.drain_sync()
        assert len(records) == 5

    def test_full_queue_does_not_block(self) -> None:
        """When queue is full, emit should return immediately (drop the record)."""
        from mp_commons.observability.logging import AsyncLogHandler

        records: list[logging.LogRecord] = []

        class CollectHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        handler = AsyncLogHandler(delegate=CollectHandler(), maxsize=1)
        for i in range(10):
            r = logging.LogRecord(
                name="t", level=logging.INFO, pathname="", lineno=0,
                msg=f"m{i}", args=(), exc_info=None,
            )
            handler.emit(r)  # should not raise

    def test_async_drain(self) -> None:
        async def run() -> None:
            handler, records = self._make_handler()
            await handler.start()
            r = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="async-msg", args=(), exc_info=None,
            )
            handler.emit(r)
            await handler.stop(timeout=2.0)
            assert any(rec.msg == "async-msg" for rec in records)

        asyncio.run(run())


# ---------------------------------------------------------------------------
# §20.9  SampledLogger
# ---------------------------------------------------------------------------

class TestSampledLogger:
    """§20.9 – SampledLogger emits only 1-in-N records per level."""

    def _mock_base(self) -> MagicMock:
        m = MagicMock()
        m.bind.return_value = m
        return m

    def test_rate_1_always_emits(self) -> None:
        from mp_commons.observability.logging import SampledLogger

        base = self._mock_base()
        log = SampledLogger(base, sample_rates={"INFO": 1})
        for _ in range(5):
            log.info("event")
        assert base.info.call_count == 5

    def test_rate_10_emits_every_10th(self) -> None:
        from mp_commons.observability.logging import SampledLogger

        base = self._mock_base()
        log = SampledLogger(base, sample_rates={"DEBUG": 10})
        for _ in range(30):
            log.debug("tick")
        # calls 1, 11, 21 → 3 emitted
        assert base.debug.call_count == 3

    def test_unlisted_level_uses_default_rate(self) -> None:
        from mp_commons.observability.logging import SampledLogger

        base = self._mock_base()
        log = SampledLogger(base, default_rate=5)
        for _ in range(10):
            log.warning("x")
        # calls 1, 6 → 2 emitted
        assert base.warning.call_count == 2

    def test_error_always_emits_when_default_rate_1(self) -> None:
        from mp_commons.observability.logging import SampledLogger

        base = self._mock_base()
        log = SampledLogger(base, sample_rates={"DEBUG": 100}, default_rate=1)
        for _ in range(5):
            log.error("critical-error")
        assert base.error.call_count == 5

    def test_bind_returns_new_sampled_logger(self) -> None:
        from mp_commons.observability.logging import SampledLogger

        base = self._mock_base()
        log = SampledLogger(base, sample_rates={"INFO": 3})
        bound = log.bind(service="svc")
        assert isinstance(bound, SampledLogger)

    def test_reset_counters(self) -> None:
        from mp_commons.observability.logging import SampledLogger

        base = self._mock_base()
        log = SampledLogger(base, sample_rates={"INFO": 5})
        for _ in range(5):
            log.info("x")
        log.reset_counters()
        log.info("after-reset")
        # After reset, first call should emit again
        assert base.info.call_count == 2  # call 1 + call after reset

    def test_warn_alias(self) -> None:
        from mp_commons.observability.logging import SampledLogger

        base = self._mock_base()
        log = SampledLogger(base)
        log.warn("deprecated-event")
        assert base.warning.call_count == 1

    def test_critical_and_info_independent_counters(self) -> None:
        from mp_commons.observability.logging import SampledLogger

        base = self._mock_base()
        log = SampledLogger(base, sample_rates={"INFO": 3, "CRITICAL": 3})
        for _ in range(3):
            log.info("i")
            log.critical("c")
        # Each: 1, 4 → call 1 only (only 3 iterations)
        assert base.info.call_count == 1
        assert base.critical.call_count == 1
