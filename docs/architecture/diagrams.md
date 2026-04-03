# Architecture Diagrams

C4 model diagrams rendered with [Mermaid](https://mermaid.js.org/).

---

## Level 1 — System Context

Shows mp-commons in relation to the systems that use it.

```mermaid
C4Context
    title System Context — mp-commons

    Person(dev, "Application Developer", "Builds microservices using mp-commons")

    System(mpcommons, "mp-commons", "Python library providing CQRS, events, saga, outbox, config, observability, security and testing utilities")

    System_Ext(postgres, "PostgreSQL", "Relational data store")
    System_Ext(redis, "Redis", "Cache and pub/sub broker")
    System_Ext(kafka, "Apache Kafka", "Async event streaming")
    System_Ext(vault, "HashiCorp Vault", "Secrets management")
    System_Ext(otel, "OpenTelemetry Collector", "Traces and metrics backend")

    Rel(dev, mpcommons, "Imports and extends")
    Rel(mpcommons, postgres, "Reads/Writes via SQLAlchemy async adapter")
    Rel(mpcommons, redis, "Caches and pub/sub via Redis adapter")
    Rel(mpcommons, kafka, "Publishes domain events via Kafka adapter")
    Rel(mpcommons, vault, "Fetches secrets at startup")
    Rel(mpcommons, otel, "Exports spans and metrics via OTLP")
```

---

## Level 2 — Container

Internal package structure and dependencies.

```mermaid
C4Container
    title Container Diagram — mp-commons packages

    Container(kernel, "kernel", "Python package", "CQRS CommandBus/QueryBus, DomainEvent, Saga, Outbox")
    Container(application, "application", "Python package", "Lifecycle hooks, ASGI middleware, i18n/L10n")
    Container(config, "config", "Python package", "Settings (Pydantic), feature flags, secret providers")
    Container(observability, "observability", "Python package", "Structured logging, Prometheus metrics, OTEL tracing, health checks")
    Container(security, "security", "Python package", "JWT auth, RBAC authz, audit trail")
    Container(adapters, "adapters", "Python package", "SQLAlchemy, Redis, Kafka, Vault, httpx adapters")
    Container(testing, "testing", "Python package", "Builders, fakes, approval tests, load test runner")

    Rel(application, kernel, "Wires middleware to CommandBus/QueryBus")
    Rel(application, config, "Reads settings")
    Rel(application, observability, "Emits request traces and logs")
    Rel(application, security, "Validates JWT tokens")
    Rel(kernel, adapters, "Uses repository and messaging adapters")
    Rel(kernel, observability, "Instruments handlers with spans")
    Rel(testing, kernel, "Fakes CommandBus, EventBus for unit tests")
    Rel(testing, adapters, "In-memory fakes for all adapters")
    Rel(config, adapters, "Vault adapter for secret store")
```

---

## Level 3 — Component: CQRS Dispatch Flow

Sequence showing how a command travels through the system.

```mermaid
sequenceDiagram
    autonumber
    participant C as Caller (FastAPI handler)
    participant MB as CommandBus
    participant MW as MiddlewarePipeline
    participant H as CommandHandler
    participant OB as OutboxRepository
    participant EB as DomainEventBus

    C->>MB: dispatch(CreateOrderCommand)
    MB->>MW: execute(command, next)
    MW->>MW: LoggingMiddleware
    MW->>MW: TracingMiddleware
    MW->>MW: ValidationMiddleware
    MW->>H: handle(command)
    H->>H: apply business logic
    H->>OB: store(OrderCreatedEvent)
    H-->>MB: result
    MB-->>C: result

    Note over OB,EB: Outbox worker (background task)
    OB->>EB: publish pending events
    EB-->>OB: ack (mark published)
```

---

## Level 3 — Component: Saga Orchestration

Sequence showing a multi-step saga coordinating across services.

```mermaid
sequenceDiagram
    autonumber
    participant SE as SagaEngine
    participant S as CheckoutSaga
    participant IB as InventoryService
    participant PB as PaymentService
    participant EB as EventBus

    EB->>SE: OrderPlacedEvent
    SE->>S: start(saga_id, event)
    S->>IB: ReserveStockCommand
    IB-->>EB: StockReservedEvent
    EB->>SE: StockReservedEvent
    SE->>S: step(saga_id, event)
    S->>PB: ChargePaymentCommand
    PB-->>EB: PaymentChargedEvent
    EB->>SE: PaymentChargedEvent
    SE->>S: complete(saga_id)

    Note over S: On any failure → compensate
    S->>IB: ReleaseStockCommand
    S->>PB: RefundPaymentCommand
```

---

## Level 3 — Component: Outbox Relay

How domain events are durably delivered after the command transaction commits.

```mermaid
flowchart TD
    A[CommandHandler] -->|INSERT domain event| B[(Outbox table\nstatus=pending)]
    B -->|COMMIT transaction| C{Outbox Worker\npolling loop}
    C -->|SELECT pending events| D[Deserialise EventEnvelope]
    D --> E[MessageBus.publish]
    E -->|success| F[(Mark status=published)]
    E -->|failure| G[(Increment retry_count)]
    G -->|retry_count < max| C
    G -->|retry_count >= max| H[(Mark status=dead)]
```
