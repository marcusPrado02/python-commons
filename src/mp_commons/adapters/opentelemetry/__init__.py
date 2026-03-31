"""OpenTelemetry adapter – tracer, metrics, propagator, logging enricher,
SQLAlchemy instrumentation, and Kafka trace-context propagation.
"""
from mp_commons.adapters.opentelemetry.tracer import OtelTracer
from mp_commons.adapters.opentelemetry.metrics import OtelMetrics
from mp_commons.adapters.opentelemetry.propagator import OtelPropagator
from mp_commons.adapters.opentelemetry.enricher import OtelLoggingEnricher
from mp_commons.adapters.opentelemetry.sqlalchemy_instrumentation import (
    instrument_engine,
    uninstrument_engine,
)
from mp_commons.adapters.opentelemetry.kafka_propagation import (
    extract_trace_context,
    inject_trace_headers,
)

__all__ = [
    "OtelLoggingEnricher",
    "OtelMetrics",
    "OtelPropagator",
    "OtelTracer",
    "extract_trace_context",
    "inject_trace_headers",
    "instrument_engine",
    "uninstrument_engine",
]
