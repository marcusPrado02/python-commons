"""Unit tests for observability logging — §20."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from mp_commons.observability.logging import (
    JsonLoggerFactory,
    LogEvent,
    Logger,
    SensitiveFieldsFilter,
)
from mp_commons.kernel.security import DEFAULT_SENSITIVE_FIELDS


# ---------------------------------------------------------------------------
# LogEvent dataclass
# ---------------------------------------------------------------------------


class TestLogEvent:
    def test_basic_creation(self) -> None:
        event = LogEvent(
            level="INFO",
            message="hello",
            logger_name="test.logger",
        )
        assert event.level == "INFO"
        assert event.message == "hello"
        assert event.logger_name == "test.logger"
        assert event.correlation_id is None
        assert event.tenant_id is None
        assert event.extra == {}

    def test_timestamp_defaults_to_utc_now(self) -> None:
        event = LogEvent(level="DEBUG", message="msg", logger_name="x")
        assert event.timestamp.tzinfo is not None

    def test_with_all_fields(self) -> None:
        ts = datetime.now(timezone.utc)
        event = LogEvent(
            level="ERROR",
            message="boom",
            logger_name="my.svc",
            timestamp=ts,
            correlation_id="cid-123",
            tenant_id="tenant-1",
            extra={"key": "val"},
        )
        assert event.correlation_id == "cid-123"
        assert event.tenant_id == "tenant-1"
        assert event.extra == {"key": "val"}

    def test_is_frozen(self) -> None:
        event = LogEvent(level="INFO", message="hi", logger_name="x")
        with pytest.raises((AttributeError, TypeError)):
            event.level = "DEBUG"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SensitiveFieldsFilter (§20.2)
# ---------------------------------------------------------------------------


class TestSensitiveFieldsFilter:
    def test_redacts_known_sensitive_key(self) -> None:
        f = SensitiveFieldsFilter()
        result = f.redact({"password": "s3cr3t", "name": "alice"})
        assert result["password"] == SensitiveFieldsFilter.REDACTED
        assert result["name"] == "alice"

    def test_redacts_all_default_sensitive_fields(self) -> None:
        f = SensitiveFieldsFilter()
        data = {field: "value" for field in DEFAULT_SENSITIVE_FIELDS}
        result = f.redact(data)
        for field in DEFAULT_SENSITIVE_FIELDS:
            assert result[field] == SensitiveFieldsFilter.REDACTED

    def test_non_sensitive_untouched(self) -> None:
        f = SensitiveFieldsFilter()
        data = {"user": "bob", "action": "login"}
        result = f.redact(data)
        assert result == data

    def test_case_insensitive_key_matching(self) -> None:
        f = SensitiveFieldsFilter()
        result = f.redact({"PASSWORD": "p", "Token": "t", "normal": "ok"})
        assert result["PASSWORD"] == SensitiveFieldsFilter.REDACTED
        assert result["Token"] == SensitiveFieldsFilter.REDACTED
        assert result["normal"] == "ok"

    def test_custom_sensitive_fields(self) -> None:
        f = SensitiveFieldsFilter(sensitive_fields=frozenset({"secret_key"}))
        result = f.redact({"secret_key": "abc", "password": "keep"})
        assert result["secret_key"] == SensitiveFieldsFilter.REDACTED
        assert result["password"] == "keep"

    def test_empty_dict(self) -> None:
        f = SensitiveFieldsFilter()
        assert f.redact({}) == {}

    def test_redact_deep_nested(self) -> None:
        f = SensitiveFieldsFilter()
        data: dict[str, Any] = {
            "user": "alice",
            "credentials": {
                "password": "hunter2",
                "token": "abc123",
            },
        }
        result = f.redact_deep(data)
        assert result["user"] == "alice"
        assert result["credentials"]["password"] == SensitiveFieldsFilter.REDACTED
        assert result["credentials"]["token"] == SensitiveFieldsFilter.REDACTED

    def test_redact_deep_non_sensitive_nested(self) -> None:
        f = SensitiveFieldsFilter()
        data: dict[str, Any] = {"outer": {"inner": "value"}}
        result = f.redact_deep(data)
        assert result == {"outer": {"inner": "value"}}

    def test_redact_does_not_modify_original(self) -> None:
        f = SensitiveFieldsFilter()
        original = {"password": "secret", "name": "alice"}
        f.redact(original)
        assert original["password"] == "secret"


# ---------------------------------------------------------------------------
# Logger protocol smoke test (§20.1)
# ---------------------------------------------------------------------------


class StubLogger:
    """Minimal Logger protocol implementation for smoke testing."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def debug(self, event: str, **kw: Any) -> None:
        self.calls.append(("debug", event))

    def info(self, event: str, **kw: Any) -> None:
        self.calls.append(("info", event))

    def warning(self, event: str, **kw: Any) -> None:
        self.calls.append(("warning", event))

    def error(self, event: str, **kw: Any) -> None:
        self.calls.append(("error", event))

    def critical(self, event: str, **kw: Any) -> None:
        self.calls.append(("critical", event))


class TestLoggerProtocol:
    def test_stub_satisfies_protocol(self) -> None:
        logger: Logger = StubLogger()  # type: ignore[assignment]
        logger.info("test message")
        logger.debug("dbg")
        logger.warning("warn")
        logger.error("err")
        logger.critical("crit")
        assert len(logger.calls) == 5  # type: ignore[attr-defined]

    def test_all_levels_callable(self) -> None:
        logger = StubLogger()
        for level in ("debug", "info", "warning", "error", "critical"):
            getattr(logger, level)("msg")
        assert len(logger.calls) == 5


# ---------------------------------------------------------------------------
# JsonLoggerFactory (§20.4)
# ---------------------------------------------------------------------------


class TestJsonLoggerFactory:
    def test_configure_does_not_raise(self) -> None:
        """configure() should work with or without structlog installed."""
        import logging
        JsonLoggerFactory.configure(level=logging.WARNING)

    def test_configure_with_sensitive_fields(self) -> None:
        import logging
        JsonLoggerFactory.configure(
            level=logging.DEBUG,
            sensitive_fields=frozenset({"my_secret"}),
        )


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.observability.logging")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing"
