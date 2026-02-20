# ADR-0002 — Outbox / Inbox / Idempotency Pattern

**Status:** Accepted  
**Date:** 2026-01-01  
**Deciders:** Platform Team

---

## Context

Distributed services need at-least-once delivery guarantees for domain events
while avoiding duplicate processing and maintaining transactional consistency
between the database write and the message publish step.

## Decision

We implement three complementary patterns:

### Outbox (producer side)

1. Domain events are written to an `outbox_records` table **in the same
   database transaction** as the aggregate change.
2. A background `OutboxDispatcher` polls the table and publishes to the
   message broker (Kafka / NATS / RabbitMQ).
3. After a successful publish the record is marked dispatched.

Port: `OutboxRepository` + `OutboxDispatcher` in `mp_commons.kernel.messaging`.  
Adapter: `SqlAlchemyOutboxRepository`, `KafkaOutboxDispatcher`.

### Inbox (consumer side)

1. Incoming messages are written to an `inbox_records` table before
   processing.
2. A handler processes the record; success marks it `processed`.
3. Duplicate detection uses `(message_id, consumer_group)` as a unique key.

Port: `InboxRepository` in `mp_commons.kernel.messaging`.

### Idempotency (use-case level)

1. Before executing a command the `IdempotencyStore` is checked; if the key
   exists the cached response is returned.
2. After execution the result is stored with a configurable TTL.

Port: `IdempotencyStore` in `mp_commons.kernel.messaging`.  
Adapters: `RedisIdempotencyStore`, `SqlAlchemyIdempotencyStore`.

## Consequences

- Guaranteed at-least-once delivery from producers.
- Idempotent consumers via inbox deduplication.
- Use-case idempotency survives client retries.
- Additional tables required: `outbox_records`, `inbox_records`,
  `idempotency_keys`.
- The `IdempotencyMiddleware` in `application.pipeline` provides transparent
  idempotency without handler code changes.
