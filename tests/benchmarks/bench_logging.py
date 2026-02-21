"""§47.5 — Benchmark: Structured logging throughput.

Measures the throughput of ``SensitiveFieldsFilter.redact()`` with and
without nested-dict traversal, as well as the ``CorrelationProcessor``
binding overhead.

When ``structlog`` is installed, the benchmarks also measure the cost of
a fully configured JSON log line.
"""

from __future__ import annotations

import logging
import uuid

from mp_commons.observability.logging.filters import SensitiveFieldsFilter

try:
    import structlog  # type: ignore[import-untyped]
    _HAS_STRUCTLOG = True
except ImportError:
    _HAS_STRUCTLOG = False

# ---------------------------------------------------------------------------
# Shared data
# ---------------------------------------------------------------------------

_FLAT_EVENT: dict = {
    "user_id": "user-1",
    "email": "alice@example.com",
    "password": "s3cr3t",
    "action": "login",
    "ip": "127.0.0.1",
}

_NESTED_EVENT: dict = {
    "user": {
        "id": "user-1",
        "email": "alice@example.com",
        "password": "s3cr3t",
    },
    "request": {
        "path": "/api/orders",
        "authorization": "Bearer tok",
        "body": {"credit_card": "4111111111111111"},
    },
    "status": 200,
}

_CLEAN_EVENT: dict = {
    "user_id": "user-1",
    "action": "view_catalog",
    "product_id": "prod-42",
    "count": 10,
}

# ---------------------------------------------------------------------------
# §47.5 a) SensitiveFieldsFilter.redact — flat dict
# ---------------------------------------------------------------------------


def test_sensitive_filter_redact_flat(benchmark):
    """``SensitiveFieldsFilter.redact()`` on a flat dict with 2 sensitive keys."""
    sf = SensitiveFieldsFilter()

    result = benchmark(sf.redact, _FLAT_EVENT)
    assert result["password"] == "[REDACTED]"
    assert result["action"] == "login"  # non-sensitive key preserved


def test_sensitive_filter_redact_flat_no_hits(benchmark):
    """``SensitiveFieldsFilter.redact()`` on a dict with no sensitive keys."""
    sf = SensitiveFieldsFilter()

    result = benchmark(sf.redact, _CLEAN_EVENT)
    assert result["user_id"] == "user-1"


def test_sensitive_filter_redact_deep(benchmark):
    """``SensitiveFieldsFilter.redact_deep()`` on a nested dict."""
    sf = SensitiveFieldsFilter()

    result = benchmark(sf.redact_deep, _NESTED_EVENT)
    assert result["user"]["password"] == "[REDACTED]"
    assert result["request"]["authorization"] == "[REDACTED]"
    assert result["request"]["body"]["credit_card"] == "[REDACTED]"


def test_sensitive_filter_redact_deep_no_hits(benchmark):
    """``SensitiveFieldsFilter.redact_deep()`` on a clean nested dict."""
    sf = SensitiveFieldsFilter()

    clean_nested = {"order": {"id": "o-1", "total": 99.9}, "status": "ok"}
    result = benchmark(sf.redact_deep, clean_nested)
    assert result["order"]["id"] == "o-1"


def test_sensitive_filter_custom_fields(benchmark):
    """``SensitiveFieldsFilter`` with a custom sensitive field set."""
    sf = SensitiveFieldsFilter(frozenset({"action", "ip"}))

    result = benchmark(sf.redact, _FLAT_EVENT)
    assert result["action"] == "[REDACTED]"
    assert result["ip"] == "[REDACTED]"
    # non-custom fields not redacted (unless in default set)
    assert result["user_id"] == "user-1"


# ---------------------------------------------------------------------------
# §47.5 b) stdlib logging call — baseline
# ---------------------------------------------------------------------------


def test_stdlib_logging_disabled_level(benchmark):
    """stdlib Logger.debug() when DEBUG is disabled (common production level)."""
    logger = logging.getLogger("bench.logging")
    logger.setLevel(logging.WARNING)

    def log():
        logger.debug("event", extra={"user_id": "u-1", "action": "login"})

    benchmark(log)  # very fast: single level-check, no formatting


def test_stdlib_logging_info_null_handler(benchmark):
    """stdlib Logger.info() with a NullHandler (no I/O overhead)."""
    logger = logging.getLogger("bench.logging.info")
    logger.handlers = [logging.NullHandler()]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    def log():
        logger.info("order_placed", extra={"order_id": str(uuid.uuid4())})

    benchmark(log)


# ---------------------------------------------------------------------------
# §47.5 c) structlog (skipped if not installed)
# ---------------------------------------------------------------------------


def test_structlog_bind_context(benchmark):
    """structlog.contextvars.bind_contextvars — binding overhead."""
    if not _HAS_STRUCTLOG:
        import pytest
        pytest.skip("structlog not installed")

    def bind():
        structlog.contextvars.bind_contextvars(correlation_id=str(uuid.uuid4()))

    benchmark(bind)


def test_structlog_log_event(benchmark):
    """structlog.get_logger().info() with bound context."""
    if not _HAS_STRUCTLOG:
        import pytest
        pytest.skip("structlog not installed")

    structlog.configure(
        processors=[structlog.processors.JSONRenderer()],
        logger_factory=structlog.PrintLoggerFactory(open("/dev/null", "w")),
        cache_logger_on_first_use=True,
    )
    log = structlog.get_logger("bench")

    def _log():
        log.info("order_placed", order_id="o-1", user_id="u-1")

    benchmark(_log)
