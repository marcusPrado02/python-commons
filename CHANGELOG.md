# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] – 2026-04-01

### Added

#### Adapters (§48–§57)
- **Elasticsearch** (`mp_commons.adapters.elasticsearch`) — `ElasticsearchClient`, `ElasticsearchSearchQuery`, `ElasticsearchRepository`; DSL search, index/get/delete/search round-trips
- **S3** (`mp_commons.adapters.s3`) — `S3ObjectStore`; CRUD, presigned URLs, MinIO-compatible endpoint override
- **Celery** (`mp_commons.adapters.celery`) — `CeleryTaskDispatcher`, `CeleryTaskRouter`; Celery task dispatch via CQRS command bus
- **gRPC** (`mp_commons.adapters.grpc`) — `GrpcChannel`, `GrpcServerFactory`; client/server lifecycle management; `CorrelationIdClientInterceptor`
- **GraphQL** (`mp_commons.adapters.graphql`) — `GraphQLClient`, `GraphQLRepository`; async query/mutation with retry
- **WebSocket** (`mp_commons.adapters.websocket`) — `WebSocketSession`, `WebSocketHub`; message fanout and graceful disconnect
- **DynamoDB** (`mp_commons.adapters.dynamodb`) — `DynamoDBRepository`, `DynamoDBTable`, `DynamoDBOutboxStore`; LocalStack-compatible
- **Cassandra** (`mp_commons.adapters.cassandra`) — `CassandraSessionFactory`, `CassandraRepository`; prepared statement cache
- **Redis Streams** (`mp_commons.adapters.redis.streams`) — `RedisStreamProducer`, `RedisStreamConsumerGroup`, `RedisStreamOutboxDispatcher`
- **Apache Pulsar** (`mp_commons.adapters.pulsar`) — `PulsarProducer`, `PulsarConsumer`; async context managers
- **Azure Service Bus** (`mp_commons.adapters.azure_servicebus`) — `AzureServiceBusProducer`, `AzureServiceBusConsumer`; managed identity auth
- **Azure Blob Storage** (`mp_commons.adapters.azure_blob`) — `AzureBlobObjectStore`; SAS presigned URLs
- **Azure Key Vault** (`mp_commons.adapters.azure_keyvault`) — `AzureKeyVaultSecretStore`; `DefaultAzureCredential`
- **Google Cloud Pub/Sub** (`mp_commons.adapters.gcp_pubsub`) — `PubSubProducer`, `PubSubSubscriber`; push/pull subscription
- **Google Cloud Storage** (`mp_commons.adapters.gcs`) — `GCSObjectStore`; mirrors S3 adapter API
- **SendGrid** (`mp_commons.adapters.sendgrid`) — `SendGridEmailSender`; template IDs, dynamic data, attachments
- **Mailgun** (`mp_commons.adapters.mailgun`) — `MailgunEmailSender`; US/EU region routing
- **AWS SQS** (`mp_commons.adapters.sqs`) — `SQSTaskBus`; FIFO queues, delay seconds, message group ID
- **OpenSearch** (`mp_commons.adapters.opensearch`) — `OpenSearchClient`, `OpenSearchRepository`; drop-in replacement for Elasticsearch
- **Prometheus** (`mp_commons.adapters.prometheus`) — `PrometheusMetricsRegistry`, FastAPI `/metrics` router, `PrometheusHealthExporter`

#### Security (§93–§100, S-series)
- **PKCE helpers** (`mp_commons.kernel.security`) — `generate_code_verifier`, `compute_code_challenge`, `verify_code_challenge`, `generate_pkce_pair`; RFC 7636 S256 method
- **Incoming Webhook Middleware** (`mp_commons.kernel.security.middleware`) — `IncomingWebhookMiddleware`; HMAC-SHA256 `X-Hub-Signature-256` verification
- **Security Headers Middleware** (`mp_commons.kernel.security.middleware`) — `ContentSecurityPolicyMiddleware`; CSP, HSTS, X-Frame-Options, Referrer-Policy
- **API Key Hash Upgrade** (`mp_commons.security.apikeys`) — `ApiKeyHashUpgrade`; bcrypt → argon2id zero-downtime migration

#### Resilience (R-series)
- **RedisCircuitBreaker** (`mp_commons.resilience.circuit_breaker`) — distributed circuit breaker state via Redis Lua scripts; atomic CLOSED→OPEN transitions
- **DeadLetterReplayScheduler** (`mp_commons.resilience`) — periodic replay of failed messages with configurable exponential backoff
- **BackpressurePolicy** (`mp_commons.resilience`) — `asyncio.Semaphore`-based backpressure for `InProcessCommandBus`
- **GracefulShutdown** (`mp_commons.resilience`) — `SIGTERM`/`SIGINT` drain with LIFO shutdown hooks and configurable timeout
- **Adapter health checks** (`mp_commons.observability.health.adapters`) — `KafkaHealthCheck`, `NatsHealthCheck`, `RabbitMQHealthCheck`, `ElasticsearchHealthCheck`

#### Observability (O-series)
- **SQLAlchemy OTel instrumentation** — wraps `AsyncSession.execute` with child spans; sanitized SQL text as span attribute
- **Kafka traceparent propagation** — injects/extracts W3C `traceparent` header in Kafka message headers
- **NATS traceparent propagation** — propagates `traceparent` in NATS message headers; extracted on consumer side
- **PrometheusHealthExporter** — exports each `HealthCheck` result as a Gauge metric
- **StructuredEvent schema_version** — `schema_version` field on `StructuredEvent`; `SchemaVersionError` for forward-compat guard; `from_dict()` deserializer

#### Developer Experience (D-series)
- **Example service** (`examples/simple_service/`) — minimal FastAPI microservice wiring `InProcessCommandBus`, correlation middleware, health router
- **Makefile `run-example` target** — boots example service with uvicorn `--reload`

#### gRPC Server Interceptors (G-series)
- `CorrelationIdServerInterceptor` — extracts `x-correlation-id` from incoming gRPC metadata
- `AuthServerInterceptor` — validates `Authorization: Bearer` JWT; aborts with `UNAUTHENTICATED` on failure
- `MetricsServerInterceptor` — records per-RPC request count and latency histogram

#### Testing (T-series)
- **`TenantIsolationValidator`** — test helper asserting no repository query leaks cross-tenant data
- **Hypothesis property tests** — `Result[T, E]` monad laws, `Money` commutativity; PII redaction fuzz tests
- **CircuitBreaker concurrency stress** — 100 concurrent coroutines; asserts consistent state machine
- **Integration tests** (requires Docker) — Elasticsearch, S3/MinIO, DynamoDB, Cassandra, Redis Streams, Apache Pulsar

#### Benchmarks (P-series)
- `bench_circuit_breaker.py` — single-call and 50-concurrent overhead (P-01)
- `bench_rate_limiter.py` — per-check latency at 1/10/100 concurrency (P-02)
- 9-middleware `InProcessCommandBus` pipeline benchmark; p50 ~10 µs, 93K ops/s (P-03)
- `AsyncLRUCache` — `maxsize`, `ttl`, `async get_or_load()` (P-04)

#### CI/CD (C-series)
- Release-drafter GitHub Action — auto-drafts changelog from PR labels (C-02)
- SBOM generation (`cyclonedx-bom`) attached as release asset (C-04)
- Mutation testing job (`mutmut`, ≥80% threshold, `workflow_dispatch` only) (C-06)
- README CI/codecov/PyPI badges (C-05)
- Docs workflow — `mkdocs build --strict` on every PR; `mkdocs gh-deploy` on `v*` tags (C-07)
- `dependabot.yml` — weekly pip + GitHub Actions version bumps (C-03)

#### Documentation
- ADR-0007: Multi-tenancy — `TenantContext` + `TenantFilter` design, trade-offs vs RLS
- ADR-0008: Event Sourcing — `EventStore`, optimistic concurrency, snapshots, schema evolution
- `docs/security/threat-model.md` — STRIDE analysis for JWT, API keys, encryption, PII, webhooks

## [0.1.0] – 2026-02-19

### Added
- **Kernel**: `errors`, `types`, `ddd`, `messaging`, `contracts`, `time`, `security`
- **Application**: `cqrs`, `pipeline`, `uow`, `pagination`, `rate_limit`, `feature_flags`
- **Resilience**: `retry`, `circuit_breaker`, `bulkhead`, `timeouts`
- **Observability**: `correlation`, `logging`, `metrics`, `tracing`
- **Config**: `settings`, `secrets`, `validation` (12-factor)
- **Adapters**: `fastapi`, `sqlalchemy`, `redis`, `kafka`, `opentelemetry`, `http`, `keycloak`, `vault`
- **Testing**: `fakes`, `fixtures`, `contracts`, `generators`, `chaos`
