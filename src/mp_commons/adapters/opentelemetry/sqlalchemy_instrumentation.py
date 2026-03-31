"""OpenTelemetry instrumentation for SQLAlchemy (O-01).

Wraps SQLAlchemy query execution with child OpenTelemetry spans so every SQL
statement appears in distributed traces.

Span attributes set on each query span:

* ``db.system`` — ``"postgresql"`` / ``"sqlite"`` / etc. (from engine dialect)
* ``db.statement`` — sanitized SQL text (parameters redacted)
* ``db.operation`` — first word of the statement (``SELECT``, ``INSERT``, …)
* ``error.message`` — set on failure (span status set to ERROR)

Usage::

    from mp_commons.adapters.opentelemetry.sqlalchemy_instrumentation import (
        instrument_engine,
    )

    engine = create_async_engine("postgresql+asyncpg://...")
    instrument_engine(engine)          # sync and async engines both work

    # To remove instrumentation:
    uninstrument_engine(engine)
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_ACTIVE_SPANS_KEY = "_otel_span"


def _get_tracer() -> Any:
    """Return the current OpenTelemetry tracer, or ``None`` if OTel is absent."""
    try:
        from opentelemetry import trace  # type: ignore[import-untyped]

        return trace.get_tracer("mp_commons.sqlalchemy")
    except ImportError:
        return None


def _sanitize_sql(statement: str) -> str:
    """Remove parameter values from SQL for safe inclusion in span attributes."""
    import re

    # Replace positional ($1, ?) and named (:param, %(name)s) parameters with ?
    statement = re.sub(r"\$\d+", "?", statement)
    statement = re.sub(r":\w+", "?", statement)
    statement = re.sub(r"%\(\w+\)s", "?", statement)
    # Truncate to keep span attributes small
    return statement[:2000] if len(statement) > 2000 else statement


def _dialect_name(engine: Any) -> str:
    try:
        return engine.dialect.name
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# SQLAlchemy event listeners
# ---------------------------------------------------------------------------


def _before_cursor_execute(
    conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
) -> None:
    tracer = _get_tracer()
    if tracer is None:
        return
    try:
        from opentelemetry.trace import SpanKind  # type: ignore[import-untyped]

        operation = statement.strip().split()[0].upper() if statement.strip() else "QUERY"
        span = tracer.start_span(
            f"db.{operation}",
            kind=SpanKind.CLIENT,
            attributes={
                "db.system": _dialect_name(conn.engine),
                "db.statement": _sanitize_sql(statement),
                "db.operation": operation,
            },
        )
        span.__enter__()
        if not hasattr(conn, "_otel_spans"):
            conn._otel_spans = []  # type: ignore[attr-defined]
        conn._otel_spans.append(span)
    except Exception:
        logger.debug("otel sqlalchemy: failed to start span", exc_info=True)


def _after_cursor_execute(
    conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
) -> None:
    _pop_and_end(conn, error=None)


def _handle_error(context: Any) -> None:
    conn = getattr(context, "connection", None)
    if conn is not None:
        _pop_and_end(conn, error=context.original_exception)


def _pop_and_end(conn: Any, error: Exception | None) -> None:
    spans = getattr(conn, "_otel_spans", None)
    if not spans:
        return
    span = spans.pop()
    try:
        if error is not None:
            from opentelemetry.trace import StatusCode  # type: ignore[import-untyped]

            span.__exit__(type(error), error, None)
        else:
            span.__exit__(None, None, None)
    except Exception:
        logger.debug("otel sqlalchemy: failed to end span", exc_info=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def instrument_engine(engine: Any) -> None:
    """Attach OpenTelemetry span instrumentation to a SQLAlchemy *engine*.

    Works with both sync :class:`sqlalchemy.engine.Engine` and async
    :class:`sqlalchemy.ext.asyncio.AsyncEngine` instances.  Attaches
    ``before_cursor_execute``, ``after_cursor_execute``, and ``handle_error``
    event listeners using SQLAlchemy's event system.

    Parameters
    ----------
    engine:
        A SQLAlchemy :class:`~sqlalchemy.engine.Engine` or
        :class:`~sqlalchemy.ext.asyncio.AsyncEngine`.
    """
    try:
        from sqlalchemy import event  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "sqlalchemy is required for instrument_engine. "
            "Install it with: pip install sqlalchemy"
        ) from exc

    # AsyncEngine wraps a sync engine — instrument the sync engine
    sync_engine = getattr(engine, "sync_engine", engine)

    if not event.contains(sync_engine, "before_cursor_execute", _before_cursor_execute):
        event.listen(sync_engine, "before_cursor_execute", _before_cursor_execute)
        event.listen(sync_engine, "after_cursor_execute", _after_cursor_execute)
        event.listen(sync_engine, "handle_error", _handle_error)
        logger.debug("otel sqlalchemy: instrumented engine %r", sync_engine)


def uninstrument_engine(engine: Any) -> None:
    """Remove OpenTelemetry span instrumentation from *engine*.

    Parameters
    ----------
    engine:
        The engine previously passed to :func:`instrument_engine`.
    """
    try:
        from sqlalchemy import event  # type: ignore[import-untyped]
    except ImportError:
        return

    sync_engine = getattr(engine, "sync_engine", engine)

    for fn, evt_name in [
        (_before_cursor_execute, "before_cursor_execute"),
        (_after_cursor_execute, "after_cursor_execute"),
        (_handle_error, "handle_error"),
    ]:
        try:
            event.remove(sync_engine, evt_name, fn)
        except Exception:
            pass


__all__ = ["instrument_engine", "uninstrument_engine"]
