"""OpenTelemetry adapter – OtelPropagator."""
from __future__ import annotations

from typing import Any

from mp_commons.observability.tracing import TracePropagator


def _require_otel() -> None:
    try:
        import opentelemetry  # noqa: F401
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[otel]' to use the OpenTelemetry adapter") from exc


class OtelPropagator(TracePropagator):
    """W3C TraceContext + Baggage propagator."""

    def __init__(self) -> None:
        _require_otel()
        from opentelemetry.propagators.b3 import B3MultiFormat  # type: ignore[import-untyped]
        self._prop = B3MultiFormat()

    def inject(self, headers: dict[str, str]) -> dict[str, str]:
        from opentelemetry.propagate import inject  # type: ignore[import-untyped]
        inject(headers)
        return headers

    def extract(self, headers: dict[str, str]) -> dict[str, Any]:
        from opentelemetry.propagate import extract  # type: ignore[import-untyped]
        ctx = extract(headers)
        return {"context": ctx}


__all__ = ["OtelPropagator"]
