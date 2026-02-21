"""Observability – structlog processors and get_logger helper.

§20.3  CorrelationProcessor — injects correlation_id/tenant_id into log events.
§20.5  get_logger(name) — returns a bound structlog logger.
"""
from __future__ import annotations

import logging
from typing import Any


class CorrelationProcessor:
    """structlog processor that injects context from :class:`CorrelationContext`.

    Injects the following fields when a :class:`RequestContext` is active:

    * ``correlation_id``
    * ``tenant_id`` (only when not ``None``)
    * ``user_id`` (only when not ``None``)
    * ``trace_id`` (only when not ``None``)

    Usage::

        import structlog
        from mp_commons.observability.logging.processors import CorrelationProcessor

        structlog.configure(processors=[CorrelationProcessor(), ...])
    """

    def __call__(
        self,
        logger: Any,           # noqa: ARG002
        method_name: str,      # noqa: ARG002
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            from mp_commons.observability.correlation import CorrelationContext

            ctx = CorrelationContext.get()
            if ctx is not None:
                event_dict.setdefault("correlation_id", ctx.correlation_id)
                if ctx.tenant_id is not None:
                    event_dict.setdefault("tenant_id", ctx.tenant_id)
                if ctx.user_id is not None:
                    event_dict.setdefault("user_id", ctx.user_id)
                if ctx.trace_id is not None:
                    event_dict.setdefault("trace_id", ctx.trace_id)
        except Exception:  # noqa: BLE001
            pass
        return event_dict


def get_logger(name: str | None = None, **initial_values: Any) -> Any:
    """Return a bound structlog logger (§20.5).

    Falls back to :func:`logging.getLogger` when structlog is not installed.

    Parameters
    ----------
    name:
        Logger name (typically ``__name__`` of the calling module).
    **initial_values:
        Key-value pairs to bind on the returned logger.
    """
    try:
        import structlog

        logger = structlog.get_logger(name)
        if initial_values:
            logger = logger.bind(**initial_values)
        return logger
    except ImportError:
        return logging.getLogger(name)


__all__ = ["CorrelationProcessor", "get_logger"]
