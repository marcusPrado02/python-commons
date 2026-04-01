"""OpenTelemetry adapter – tracer, metrics, propagator, logging enricher,
SQLAlchemy instrumentation, Kafka and NATS trace-context propagation.
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
    extract_trace_context as kafka_extract_trace_context,
    inject_trace_headers as kafka_inject_trace_headers,
)
from mp_commons.adapters.opentelemetry.nats_propagation import (
    extract_trace_context as nats_extract_trace_context,
    inject_trace_headers as nats_inject_trace_headers,
)

# Back-compat aliases (default to kafka flavour)
extract_trace_context = kafka_extract_trace_context
inject_trace_headers = kafka_inject_trace_headers

__all__ = [
    "OtelLoggingEnricher",
    "OtelMetrics",
    "OtelPropagator",
    "OtelTracer",
    "extract_trace_context",
    "inject_trace_headers",
    "instrument_engine",
    "kafka_extract_trace_context",
    "kafka_inject_trace_headers",
    "nats_extract_trace_context",
    "nats_inject_trace_headers",
    "uninstrument_engine",
]
