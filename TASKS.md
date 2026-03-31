# TASKS — mp-commons

> Tasks that still need to be done, organized by category and priority.
> This file complements `BACKLOG.md` and focuses on the remaining work.
>
> | Symbol | Meaning |
> |--------|---------|
> | ⬜ | Not started |
> | 🔵 | In progress |
> | ✅ | Done |

---

## 1. Remaining BACKLOG Items (from §42 and §48–§57)

These are the only officially open items from the 100-section BACKLOG.

| # | Task | Priority | Status |
|---|------|----------|--------|
| B-01 | **§42.1** — Create GitHub Environment named `pypi` in repository settings (required for OIDC publish job in CI) | High | ⬜ |
| B-02 | **§42.2** — Configure Trusted Publisher on PyPI — link `github.com/marcusPrado02/python-commons`, environment `pypi`, workflow `ci.yml` | High | ⬜ |
| B-03 | **§48.6** — Integration tests for Elasticsearch adapter using `testcontainers-python` — index/get/delete round-trip, DSL search returns matching docs only | High | ⬜ |
| B-04 | **§49.6** — Integration tests for S3/MinIO adapter using `testcontainers-python` — full CRUD, presigned URL accessible via HTTP GET | High | ⬜ |
| B-05 | **§54.6** — Integration tests for DynamoDB adapter using LocalStack via `testcontainers-python` — CRUD, GSI query, TTL attribute present | High | ⬜ |
| B-06 | **§55.5** — Integration tests for Cassandra adapter using `testcontainers-python` — CRUD round-trip, prepared statements reused across calls | Medium | ⬜ |
| B-07 | **§56.6** — Integration tests for Redis Streams adapter using `testcontainers-python` — produce/consume round-trip, consumer group ack, pending entry list | High | ⬜ |
| B-08 | **§57.6** — Integration tests for Apache Pulsar adapter using `testcontainers-python` — produce/consume round-trip | Medium | ⬜ |

---

## 2. CI/CD & Release Pipeline

| # | Task | Priority | Status |
|---|------|----------|--------|
| C-01 | Add a GitHub Actions job `integration-tests` that spins up Docker services (Redis, PostgreSQL, Kafka, Elasticsearch, MinIO) via `testcontainers-python` and runs the full integration suite on every PR | High | ⬜ |
| C-02 | Add `release-drafter` GitHub Action — auto-drafts `CHANGELOG.md` entries from PR labels (`feat`, `fix`, `breaking`, `chore`) on each merge to `main` | Medium | ⬜ |
| C-03 | Configure `dependabot.yml` for GitHub Actions version bumps — separate ecosystem entry from pip to keep workflow versions current | Medium | ⬜ |
| C-04 | Add SBOM (Software Bill of Materials) generation step to the release workflow using `cyclonedx-bom`; attach the `.json` SBOM as a release asset | Low | ⬜ |
| C-05 | Add `pyproject.toml` badges in `README.md` — CI status, codecov, PyPI version, Python versions, license | Low | ⬜ |
| C-06 | Add `mutation` CI job (opt-in via `workflow_dispatch`) that runs `mutmut run --use-coverage` on files changed in the PR; fails build if mutation score < 80 % | Medium | ⬜ |
| C-07 | Publish `docs` via `mkdocs gh-deploy` automatically on every `v*` tag push; ensure `mkdocs build --strict` runs as a lint step on every PR | Medium | ⬜ |

---

## 3. Missing Adapters

| # | Task | Priority | Status |
|---|------|----------|--------|
| A-01 | **Adapter — Azure Service Bus** — implement `AzureServiceBusProducer` and `AzureServiceBusConsumer` implementing the same `MessageBus` protocol as Kafka/NATS; add `azure-servicebus` optional extra | Medium | ⬜ |
| A-02 | **Adapter — Google Cloud Pub/Sub** — implement `PubSubProducer` / `PubSubSubscriber` with `google-cloud-pubsub` optional extra; support push and pull subscription modes | Medium | ⬜ |
| A-03 | **Adapter — Azure Blob Storage** — implement `AzureBlobObjectStore(ObjectStore)` using `azure-storage-blob`; supports put/get/delete/list and presigned SAS URL generation | Medium | ⬜ |
| A-04 | **Adapter — Google Cloud Storage** — implement `GCSObjectStore(ObjectStore)` using `google-cloud-storage`; mirrors S3 adapter API | Medium | ⬜ |
| A-05 | **Adapter — SendGrid** — implement `SendGridEmailSender(EmailSender)` using `sendgrid` library; support template IDs and dynamic data injection | Medium | ⬜ |
| A-06 | **Adapter — Mailgun** — implement `MailgunEmailSender(EmailSender)` via `httpx`; support EU and US region base URLs | Low | ⬜ |
| A-07 | **Adapter — AWS SQS** — implement `SQSTaskBus(TaskBus)` using `aiobotocore`; support FIFO queues, delay seconds, and message group ID | Medium | ⬜ |
| A-08 | **Adapter — Azure Key Vault** — implement `AzureKeyVaultSecretStore(SecretStore)` using `azure-keyvault-secrets`; support managed identity auth | Medium | ⬜ |
| A-09 | **Adapter — Prometheus HTTP endpoint** — implement `PrometheusMetricsRegistry(MetricsRegistry)` using `prometheus-client`; expose `/metrics` route via FastAPI router | High | ⬜ |
| A-10 | **Adapter — OpenSearch** — implement `OpenSearchRepository` as a drop-in replacement for `ElasticsearchRepository` (same DSL, different client); add `opensearch-py` optional extra | Low | ⬜ |

---

## 4. gRPC Server-Side Enhancements

| # | Task | Priority | Status |
|---|------|----------|--------|
| G-01 | Implement `CorrelationIdServerInterceptor` — extracts `x-correlation-id` from incoming gRPC metadata and sets `CorrelationContext`; mirrors the existing client interceptor | High | ⬜ |
| G-02 | Implement `AuthServerInterceptor` — validates Bearer JWT from incoming `authorization` metadata; sets `SecurityContext`; raises `UNAUTHENTICATED` on failure | High | ⬜ |
| G-03 | Implement `MetricsServerInterceptor` — records per-RPC request count and latency histogram via `MetricsRegistry` | Medium | ⬜ |
| G-04 | Add unit tests for all three gRPC server interceptors using `grpcio-testing` helpers | High | ⬜ |

---

## 5. Observability & Tracing Improvements

| # | Task | Priority | Status |
|---|------|----------|--------|
| O-01 | Add OpenTelemetry auto-instrumentation for SQLAlchemy queries — wrap `AsyncSession.execute` calls with child spans including sanitized SQL text as span attribute | High | ⬜ |
| O-02 | Propagate `traceparent` / `tracestate` headers in Kafka message headers so distributed traces span across producers and consumers | High | ⬜ |
| O-03 | Propagate `traceparent` in NATS message headers; extract on consumer side in `NatsMessageBus` | Medium | ⬜ |
| O-04 | Implement `PrometheusHealthExporter` — exports each `HealthCheck` result as a Gauge metric (`mp_commons_health_check{name="db"} 1.0`) | Medium | ⬜ |
| O-05 | Add `StructuredEvent` schema version field and enforce backward-compatible schema evolution in `EventEmitter` | Low | ⬜ |

---

## 6. Resilience & Reliability Improvements

| # | Task | Priority | Status |
|---|------|----------|--------|
| R-01 | Implement `BackpressurePolicy` for `InProcessCommandBus` — track in-flight commands via `asyncio.Semaphore`; raise `BackpressureError` when queue depth exceeds configured threshold | High | ⬜ |
| R-02 | Implement `GracefulShutdown` utility — listens for `SIGTERM`/`SIGINT`; drains in-flight coroutines; calls registered shutdown hooks in LIFO order; configurable drain timeout | High | ⬜ |
| R-03 | Implement multi-region circuit breaker state sharing via Redis — `RedisCircuitBreaker` stores state in Redis key so all instances of a service share the same breaker state | Medium | ⬜ |
| R-04 | Add `DeadLetterReplayScheduler` — periodic job that queries `DeadLetterStore` and replays failed messages with configurable backoff between attempts | Medium | ⬜ |
| R-05 | Add structured healthchecks for each major adapter — `KafkaHealthCheck`, `NatsHealthCheck`, `RabbitMQHealthCheck`, `ElasticsearchHealthCheck`; register with `HealthRegistry` | High | ⬜ |

---

## 7. Security Hardening

| # | Task | Priority | Status |
|---|------|----------|--------|
| S-01 | Add `TenantIsolationValidator` — test helper that verifies no repository query returns data belonging to a different tenant; raises `TenantLeakError` in test mode | High | ⬜ |
| S-02 | Implement incoming webhook signature verification middleware — `IncomingWebhookMiddleware` (FastAPI) verifies `X-Hub-Signature-256` header on `POST /webhooks/*` routes | High | ⬜ |
| S-03 | Add `PKCE` support to `OIDCTokenVerifier` — validate `code_challenge_method` and `code_verifier` in authorization code flow | Medium | ⬜ |
| S-04 | Implement `ContentSecurityPolicyMiddleware` (FastAPI) — adds CSP, HSTS, X-Frame-Options, Referrer-Policy headers to all responses; configurable per-route overrides | Medium | ⬜ |
| S-05 | Add `ApiKeyHashUpgrade` migration helper — re-hashes existing `bcrypt` API key hashes to `argon2` when a key is next verified; zero-downtime algorithm migration | Low | ⬜ |

---

## 8. Developer Experience & Tooling

| # | Task | Priority | Status |
|---|------|----------|--------|
| D-01 | Create `examples/` directory with a minimal working FastAPI microservice — wires up Command Bus, SQLAlchemy UoW, structured logging, health checks, and correlation middleware | High | ⬜ |
| D-02 | Add a `Makefile` target `run-example` that boots the example service with `uvicorn` and seeds the database via Alembic migrations | Medium | ⬜ |
| D-03 | Generate `.pyi` type stub files for the public API (all `__init__.py` re-exports) so IDEs offer completion without traversing the full source tree | Medium | ⬜ |
| D-04 | Write `docs/guides/troubleshooting.md` — covers common async pitfalls (event loop reuse, fixture scoping, context var isolation), adapter import errors, and mypy strict mode issues | High | ⬜ |
| D-05 | Write `docs/guides/migration-v1.md` — documents any breaking changes from pre-1.0 to 1.0.0 and provides a step-by-step upgrade guide | Medium | ⬜ |
| D-06 | Add per-adapter runbooks in `docs/adapters/` — each runbook covers: installation, required env vars, health check endpoint, common error codes, performance tuning tips | Medium | ⬜ |
| D-07 | Add a `devcontainer.json` configuration (VS Code Dev Containers) — pre-installs `uv`, project deps, and starts all required Docker services for local development | Low | ⬜ |

---

## 9. Advanced Testing

| # | Task | Priority | Status |
|---|------|----------|--------|
| T-01 | Add end-to-end integration test covering the full command → domain event → outbox → Kafka → consumer → inbox deduplication flow using real containers | High | ⬜ |
| T-02 | Add integration tests for `Keycloak` adapter against a real Keycloak container via `testcontainers-python` — token verify, expired token, wrong audience | Medium | ⬜ |
| T-03 | Add integration tests for `Vault` adapter against a Vault dev server container — `SecretStore.get`, `SecretStore.get_all`, token renewal | Medium | ⬜ |
| T-04 | Add integration tests for the full `Saga` orchestration with real PostgreSQL — persist saga state, resume after failure, verify compensation was recorded | High | ⬜ |
| T-05 | Add `hypothesis`-based property tests for `Result[T, E]` — `map` / `flat_map` laws (identity, associativity, monad laws) | Medium | ⬜ |
| T-06 | Add `hypothesis`-based property tests for `Money` — commutativity of `add`, currency mismatch always raises, `multiply` never returns negative for positive inputs | Medium | ⬜ |
| T-07 | Add fuzz testing for PII redaction patterns — generate random strings containing email, CPF, phone, and credit card sub-patterns; assert no false negatives | Medium | ⬜ |
| T-08 | Add concurrency stress test for `CircuitBreaker` — 100 concurrent coroutines hitting a failing backend; assert state machine never enters an inconsistent state | High | ⬜ |
| T-09 | Add integration tests for `MongoDB` adapter against a real MongoDB container — repository CRUD, optimistic locking, outbox lifecycle, TTL index | Medium | ⬜ |
| T-10 | Verify `anyio` trio backend compatibility — run the full unit test suite under `pytest-anyio` with `backend="trio"`; fix any trio-incompatible patterns | Medium | ⬜ |

---

## 10. Performance & Benchmarking

| # | Task | Priority | Status |
|---|------|----------|--------|
| P-01 | Add benchmark for `CircuitBreaker.call` under concurrent load — measure throughput with 50 concurrent coroutines; assert overhead < 5 % compared to bare call | Medium | ⬜ |
| P-02 | Add benchmark for `RedisSlidingWindowRateLimiter` — latency per `acquire()` call against a real Redis container; target p99 < 5 ms | Medium | ⬜ |
| P-03 | Profile `InProcessCommandBus` with 9-middleware pipeline at 10 000 dispatches/s — identify top allocation hotspots via `memory_profiler` and reduce object creation | Medium | ⬜ |
| P-04 | Add `AsyncLRUCache` in-process cache implementation as an alternative to Redis for low-cardinality, read-heavy keys — `maxsize`, `ttl`, `async get_or_load(key, loader)` | Low | ⬜ |

---

## 11. Documentation Completeness

| # | Task | Priority | Status |
|---|------|----------|--------|
| DOC-01 | Update `CHANGELOG.md` with entries for all sections §48–§100 (current entries are missing for the second half of the backlog) | High | ⬜ |
| DOC-02 | Add architecture decision record `ADR-0007-multi-tenancy.md` — documents the `TenantContext` + `TenantFilter` approach, trade-offs vs row-level security, and how to opt out | Medium | ⬜ |
| DOC-03 | Add architecture decision record `ADR-0008-event-sourcing.md` — documents `EventStore` design, optimistic concurrency approach, snapshot strategy, and integration with `ProjectionStore` | Medium | ⬜ |
| DOC-04 | Add `docs/security/threat-model.md` — STRIDE analysis for the library's security primitives: JWT verification, API key management, encryption, PII redaction | Medium | ⬜ |
| DOC-05 | Ensure all public classes and functions have complete docstrings — run `mkdocstrings` in strict mode and fix every missing/incomplete docstring in the public API surface | High | ⬜ |

---

## Summary

| Category | Total Tasks |
|----------|------------|
| Remaining BACKLOG (§42, §48–§57) | 8 |
| CI/CD & Release Pipeline | 7 |
| Missing Adapters | 10 |
| gRPC Server-Side Enhancements | 4 |
| Observability & Tracing | 5 |
| Resilience & Reliability | 5 |
| Security Hardening | 5 |
| Developer Experience & Tooling | 7 |
| Advanced Testing | 10 |
| Performance & Benchmarking | 4 |
| Documentation Completeness | 5 |
| **Total** | **70** |
