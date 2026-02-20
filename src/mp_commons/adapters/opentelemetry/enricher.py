"""OpenTelemetry adapter – OtelLoggingEnricher."""
from __future__ import annotations

from typing import Any


class OtelLoggingEnricher:
    """structlog processor that injects current span's trace/span IDs."""

    def __call__(self, logger: Any, method: Any, event_dict: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG002
        try:
            from opentelemetry import trace  # type: ignore[import-untyped]
            span = trace.get_current_span()
            ctx = span.get_span_context()
            if ctx.is_valid:
                event_dict["trace_id"] = format(ctx.trace_id, "032x")
                event_dict["span_id"] = format(ctx.span_id, "016x")
        except Exception:  # noqa: BLE001
            pass
        return event_dict


__all__ = ["OtelLoggingEnricher"]
