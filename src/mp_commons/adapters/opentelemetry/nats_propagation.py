"""W3C traceparent propagation for NATS messages (O-03).

Injects/extracts the W3C ``traceparent`` header into NATS message headers
(``nats-py`` ≥2.2 ``nats.aio.msg.Msg.headers`` dict-like).

Usage (publisher)::

    from mp_commons.adapters.opentelemetry.nats_propagation import inject_trace_headers

    headers = {}
    inject_trace_headers(headers)
    await js.publish("orders", payload, headers=headers)

Usage (subscriber)::

    from mp_commons.adapters.opentelemetry.nats_propagation import extract_trace_context

    token = extract_trace_context(msg.headers or {})
    try:
        await process(msg)
    finally:
        if token is not None:
            context.detach(token)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _get_propagator() -> Any | None:
    try:
        from opentelemetry.propagate import get_global_textmap

        return get_global_textmap()
    except ImportError:
        return None


def _get_context_api() -> Any | None:
    try:
        from opentelemetry import context

        return context
    except ImportError:
        return None


class _NatsHeaderCarrier:
    """Adapter that maps the OTel TextMap API to a NATS headers dict.

    NATS headers are ``dict[str, str]`` (nats-py uses ``nats.aio.msg.Headers``
    which behaves like a dict).  The carrier acts as its own getter/setter so
    the propagator can call ``carrier.get(key)`` and ``carrier.set(key, value)``.
    """

    def __init__(self, headers: dict[str, str]) -> None:
        self._headers = headers

    def get(self, key: str) -> list[str]:
        value = self._headers.get(key)
        if value is None:
            return []
        return [value]

    def keys(self) -> list[str]:
        return list(self._headers.keys())

    def set(self, key: str, value: str) -> None:
        self._headers[key] = value


def inject_trace_headers(headers: dict[str, str]) -> None:
    """Inject the current trace context into *headers* as a ``traceparent`` entry.

    No-op when OpenTelemetry is not installed or no active span exists.

    Parameters
    ----------
    headers:
        Mutable dict that will be passed as ``headers=`` to ``js.publish()``.
    """
    propagator = _get_propagator()
    if propagator is None:
        return
    try:
        carrier = _NatsHeaderCarrier(headers)
        propagator.inject(carrier)
    except Exception:
        logger.debug("nats_propagation: failed to inject trace headers", exc_info=True)


def extract_trace_context(headers: dict[str, str] | None) -> object | None:
    """Extract trace context from *headers* and attach it to the current context.

    Returns
    -------
    token
        A context token that must be passed to ``opentelemetry.context.detach``
        after processing completes.  Returns ``None`` when OTel is unavailable
        or no trace context was found in the headers.
    """
    if not headers:
        return None
    propagator = _get_propagator()
    if propagator is None:
        return None
    context_api = _get_context_api()
    if context_api is None:
        return None
    try:
        carrier = _NatsHeaderCarrier(headers)
        ctx = propagator.extract(carrier)
        token = context_api.attach(ctx)
        return token
    except Exception:
        logger.debug("nats_propagation: failed to extract trace context", exc_info=True)
        return None


__all__ = ["extract_trace_context", "inject_trace_headers"]
