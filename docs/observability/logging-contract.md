# Logging Contract

All structured logs emitted by services using `mp-commons` **must** conform
to this schema.  Formatters configured via `JsonLoggerFactory.configure()`
produce compliant output automatically.

---

## Required Fields

| Field | Type | Description |
|---|---|---|
| `timestamp` | ISO-8601 UTC string | When the event occurred |
| `level` | `DEBUG \| INFO \| WARNING \| ERROR \| CRITICAL` | Log severity |
| `logger` | string | Logger name / module path |
| `message` | string | Human-readable description |
| `correlation_id` | string (ULID/UUID) | Request correlation identifier |
| `service` | string | Service name from config |
| `environment` | string | `production`, `staging`, `development` |

## Optional Fields

| Field | Type | Description |
|---|---|---|
| `tenant_id` | string | Multi-tenant context |
| `user_id` | string | Authenticated user |
| `trace_id` | string | OpenTelemetry trace ID |
| `span_id` | string | OpenTelemetry span ID |
| `error.type` | string | Exception class name |
| `error.message` | string | Exception message |
| `error.stack_trace` | string | Full traceback |
| `duration_ms` | number | Elapsed time in milliseconds |

## PII Redaction

Fields listed in `DEFAULT_SENSITIVE_FIELDS` (and any additions registered
via `PIIRedactor`) are replaced with `"[REDACTED]"` before the log entry
is emitted.

Default sensitive fields: `password`, `secret`, `token`, `api_key`,
`authorization`, `credit_card`, `ssn`, `cpf`, `cnpj`.

## Example

```json
{
  "timestamp": "2026-01-15T14:23:11.456Z",
  "level": "INFO",
  "logger": "orders.application.create_order",
  "message": "Order created successfully",
  "correlation_id": "01HX4K9J2E3N5P7Q8R0STUVWXY",
  "service": "orders-service",
  "environment": "production",
  "tenant_id": "tenant-acme",
  "user_id": "usr-42",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "duration_ms": 47
}
```
