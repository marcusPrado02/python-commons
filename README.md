# mp-commons

**Platform shared library for Python microservices.**

`mp-commons` delivers the "senior engineer pillars" as importable building
blocks so every service starts from a solid foundation without re-inventing
the wheel:

- **DDD / Hexagonal Architecture** — Entities, Value Objects, Aggregates,
  Domain Events, Repositories, Unit of Work
- **CQRS** — Command / Query buses with an in-process default
- **Resilience** — Retry (exponential + jitter), Circuit Breaker, Bulkhead,
  Timeouts
- **Outbox / Inbox / Idempotency** — at-least-once delivery with duplicate
  suppression
- **Observability** — structured logging, metrics, tracing (all via ports)
- **Security** — Principal, Policy Engine, PII redaction, OIDC/Keycloak
  adapter
- **12-factor Config** — env-var loader, Kubernetes secrets, Vault
- **Contract Testing** — OpenAPI / AsyncAPI compatibility assertions
- **Testing Support** — in-memory fakes, pytest fixtures, chaos injection

---

## Installation

```bash
# Core only (no third-party runtime deps)
pip install mp-commons

# With specific adapters
pip install "mp-commons[fastapi,sqlalchemy,redis,otel]"

# Everything
pip install "mp-commons[all-adapters]"
```

Available extras: `fastapi`, `sqlalchemy`, `redis`, `kafka`, `nats`,
`rabbitmq`, `httpx`, `keycloak`, `vault`, `otel`, `pydantic`, `structlog`,
`tenacity`, `crypto`, `dotenv`.

---

## Quick Start

### 1. Define a Domain

```python
from dataclasses import dataclass
from mp_commons.kernel.ddd import AggregateRoot, DomainEvent, Invariant
from mp_commons.kernel.types import EntityId

@dataclass(frozen=True)
class OrderPlaced(DomainEvent):
    order_id: str
    event_type: str = "order.placed"

@dataclass
class Order(AggregateRoot):
    customer_id: str
    total_cents: int

    def place(self) -> None:
        Invariant.require(self.total_cents > 0, "Total must be positive")
        self._raise_event(OrderPlaced(order_id=str(self.id)))
```

### 2. Write a Use Case with CQRS

```python
from mp_commons.application.cqrs import Command, CommandHandler, InProcessCommandBus

class PlaceOrderCommand(Command):
    def __init__(self, customer_id: str, total_cents: int) -> None:
        self.customer_id = customer_id
        self.total_cents = total_cents

class PlaceOrderHandler(CommandHandler[PlaceOrderCommand]):
    async def handle(self, cmd: PlaceOrderCommand) -> None:
        order = Order(id=EntityId.generate(), customer_id=cmd.customer_id, total_cents=cmd.total_cents)
        order.place()

bus = InProcessCommandBus()
bus.register(PlaceOrderCommand, PlaceOrderHandler())
await bus.dispatch(PlaceOrderCommand("cust-1", 1999))
```

### 3. Add Resilience

```python
from mp_commons.resilience.retry import RetryPolicy, ExponentialBackoff, FullJitter
from mp_commons.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerPolicy

retry = RetryPolicy(max_attempts=3, backoff=ExponentialBackoff(base=0.1), jitter=FullJitter())
cb = CircuitBreaker("payments", CircuitBreakerPolicy(failure_threshold=5))

result = await retry.execute_async(lambda: cb.call(call_payment_service))
```

### 4. Structured Logging with Correlation

```python
from mp_commons.observability.logging import JsonLoggerFactory
from mp_commons.observability.correlation import CorrelationContext, RequestContext

JsonLoggerFactory.configure(service="orders-service", environment="production")
ctx = RequestContext.new(tenant_id=TenantId("acme"))
CorrelationContext.set(ctx)

import structlog
log = structlog.get_logger()
log.info("order_placed", order_id="ord-1")
```

### 5. FastAPI Integration

```python
from fastapi import FastAPI
from mp_commons.adapters.fastapi import (
    FastAPICorrelationIdMiddleware,
    FastAPIExceptionMapper,
    FastAPIHealthRouter,
)

app = FastAPI()
app.add_middleware(FastAPICorrelationIdMiddleware)
FastAPIExceptionMapper.register(app)
app.include_router(FastAPIHealthRouter())
```

### 6. Testing with Fakes

```python
from mp_commons.testing.fakes import FakeClock, InMemoryMessageBus, FakePolicyEngine
from mp_commons.kernel.security import PolicyDecision

clock = FakeClock()
bus = InMemoryMessageBus()
policy = FakePolicyEngine(default=PolicyDecision.ALLOW)

await bus.publish(some_message)
assert len(bus.of_topic("orders")) == 1
clock.advance(hours=2)
```

---

## Module Map

```
mp_commons/
├── kernel/          # Zero external deps — pure Python
│   ├── errors/      # Error hierarchy
│   ├── types/       # EntityId, Money, Email, Result, Option, …
│   ├── ddd/         # Entity, Aggregate, ValueObject, DomainEvent, Specification, …
│   ├── messaging/   # Message, Outbox, Inbox, Idempotency ports
│   ├── contracts/   # CompatibilityMode, ContractRegistry port
│   ├── time/        # Clock protocol, SystemClock, FrozenClock
│   └── security/    # Principal, PolicyEngine, CryptoProvider, PIIRedactor
├── application/     # Use-case layer
│   ├── cqrs/        # Command/Query buses
│   ├── pipeline/    # Middleware pipeline + 9 built-in middlewares
│   ├── pagination/  # Page, PageRequest, Cursor
│   ├── rate_limit/  # RateLimiter port
│   ├── feature_flags/ # FeatureFlagProvider port
│   └── uow/         # TransactionManager, @transactional
├── resilience/
│   ├── retry/       # RetryPolicy, backoff & jitter strategies
│   ├── circuit_breaker/
│   ├── bulkhead/
│   └── timeouts/
├── observability/
│   ├── correlation/ # RequestContext, CorrelationContext (ContextVar)
│   ├── logging/     # Logger port, SensitiveFieldsFilter, JsonLoggerFactory
│   ├── metrics/     # Counter/Histogram/Gauge ports, NoopMetrics
│   └── tracing/     # Tracer/Span ports, NoopTracer
├── config/
│   ├── settings/    # Settings dataclass, EnvSettingsLoader, DotenvSettingsLoader
│   ├── secrets/     # SecretStore port, KubernetesSecretStore
│   └── validation/  # ConfigError, MissingRequiredSettingError
├── adapters/        # Concrete implementations (all lazy-imported)
│   ├── fastapi/
│   ├── sqlalchemy/
│   ├── redis/
│   ├── kafka/
│   ├── nats/
│   ├── rabbitmq/
│   ├── opentelemetry/
│   ├── http/        # httpx-based HTTP client with retry & circuit-breaker
│   ├── keycloak/    # OIDC token verification
│   └── vault/       # HashiCorp Vault secrets
└── testing/
    ├── fakes/       # In-memory doubles for all kernel ports
    ├── fixtures/    # pytest fixtures
    ├── contracts/   # OpenAPI/AsyncAPI contract test helpers
    ├── generators/  # Domain object factories
    └── chaos/       # Latency & failure injection
```

---

## Architecture Principles

1. **No framework leakage** — `kernel.*` imports stdlib only.
   See [ADR-0001](docs/architecture/ADR-0001-kernel-boundaries.md).
2. **Ports & Adapters** — every infrastructure concern is a Protocol/ABC
   in the kernel; concrete implementations live in `adapters/`.
3. **Optional extras** — no adapter is a hard dependency.
4. **Idiomatic Python 3.12+** — `type` aliases, `match`, dataclasses,
   `asyncio`-native.

---

## Development

```bash
uv sync --extra dev   # install dev deps
pytest                # run tests
ruff check src tests  # lint
mypy src              # type-check
pre-commit run --all-files
```

---

## Contributing

1. Fork and create a feature branch.
2. Write tests first.
3. Ensure `pytest`, `ruff`, and `mypy` all pass.
4. Update `CHANGELOG.md`.
5. Open a PR — CI must be green.

---

## License

MIT — see [LICENSE](LICENSE).
