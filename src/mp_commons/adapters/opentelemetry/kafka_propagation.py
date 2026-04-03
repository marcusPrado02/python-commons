"""OpenTelemetry W3C traceparent / tracestate propagation for Kafka (O-02).

Provides two helpers:

* :func:`inject_trace_headers` — inject W3C trace context into a Kafka
  message header list before producing.
* :func:`extract_trace_context` — extract the trace context from a consumed
  Kafka message header list and set it as the active context.

Usage in a producer::

    from mp_commons.adapters.opentelemetry.kafka_propagation import inject_trace_headers

    headers = [("key", b"val")]
    inject_trace_headers(headers)  # appends traceparent + tracestate
    await producer.send(topic, value=body, headers=headers)

Usage in a consumer::

    from mp_commons.adapters.opentelemetry.kafka_propagation import extract_trace_context

    async for msg in consumer:
        token = extract_trace_context(msg.headers)
        try:
            await handle(msg)
        finally:
            if token is not None:
                context_api.detach(token)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_TRACEPARENT_KEY = "traceparent"
_TRACESTATE_KEY = "tracestate"


class _KafkaHeaderCarrier:
    """Adapter between aiokafka header lists and the OTel ``Getter``/``Setter`` API."""

    def __init__(self, headers: list[tuple[str | bytes, bytes]]) -> None:
        self._headers = headers

    def get(self, key: str) -> list[str]:
        result: list[str] = []
        for k, v in self._headers:
            header_key = k.decode() if isinstance(k, bytes) else k
            if header_key.lower() == key.lower():
                result.append(v.decode("utf-8", errors="replace"))
        return result

    def set(self, key: str, value: str) -> None:
        self._headers.append((key, value.encode()))

    def keys(self) -> list[str]:
        return [(k.decode() if isinstance(k, bytes) else k) for k, _ in self._headers]


def _get_propagator() -> Any | None:
    """Return the OTel ``TextMapPropagator`` or ``None`` if OTel is absent."""
    try:
        from opentelemetry.propagate import get_global_textmap  # type: ignore[import-untyped]

        return get_global_textmap()
    except ImportError:
        return None


def inject_trace_headers(
    headers: list[tuple[str | bytes, bytes]],
) -> None:
    """Inject W3C ``traceparent`` and ``tracestate`` into *headers*.

    If OpenTelemetry is not installed or there is no active span, this
    function is a no-op.

    Parameters
    ----------
    headers:
        A mutable list of ``(key, value)`` tuples that will be sent as
        Kafka message headers.  The list is modified in-place.
    """
    propagator = _get_propagator()
    if propagator is None:
        return
    try:
        carrier = _KafkaHeaderCarrier(headers)
        propagator.inject(carrier)
    except Exception:
        logger.debug("kafka propagation: failed to inject trace headers", exc_info=True)


def extract_trace_context(
    headers: list[tuple[str | bytes, bytes]] | None,
) -> Any | None:
    """Extract trace context from Kafka message *headers* and attach it.

    Returns a ``contextvars.Token`` that must be detached after the message
    is processed to avoid context leakage::

        token = extract_trace_context(msg.headers)
        try:
            await handle(msg)
        finally:
            if token is not None:
                from opentelemetry import context as context_api

                context_api.detach(token)

    Parameters
    ----------
    headers:
        The headers list from a consumed Kafka message.

    Returns
    -------
    token:
        The ``contextvars.Token`` from ``context.attach``, or ``None`` if
        OpenTelemetry is unavailable or no trace context was found.
    """
    if not headers:
        return None
    propagator = _get_propagator()
    if propagator is None:
        return None
    try:
        from opentelemetry import context as context_api  # type: ignore[import-untyped]

        carrier = _KafkaHeaderCarrier(list(headers))
        ctx = propagator.extract(carrier)
        return context_api.attach(ctx)
    except Exception:
        logger.debug("kafka propagation: failed to extract trace context", exc_info=True)
        return None


__all__ = ["extract_trace_context", "inject_trace_headers"]
