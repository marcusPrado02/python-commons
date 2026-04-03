# ADR-0008 — Event Sourcing: EventStore Design and Integration

**Status:** Accepted
**Date:** 2026-02-15
**Deciders:** Platform Team

---

## Context

Some aggregates in the platform have audit, replay, or temporal-query
requirements that exceed what a traditional "last-write-wins" ORM model can
satisfy.  The team evaluated three approaches:

1. **Audit columns** — `created_at`, `updated_at`, `deleted_at` on every table.
   Simple, but loses intermediate state and prevents replay.
2. **Change Data Capture (CDC)** — stream Postgres WAL to an event bus.
   Requires external infrastructure and couples the schema to the event model.
3. **Event Sourcing** — persist domain events as the primary record of truth;
   derive current state by replaying events.

## Decision

We implement opt-in event sourcing via the `EventStore` port and
`EventSourcedAggregate` base class.  Services choose per-aggregate whether to
use event sourcing or the standard repository pattern.

### Core primitives

```
EventStore          — port: append(stream_id, events, expected_version)
                            load(stream_id) -> list[DomainEvent]

EventSourcedAggregate
  .apply(event)     — mutate state from a domain event
  .record(event)    — stage an uncommitted event (calls apply internally)
  .uncommitted      — list of staged events (cleared after persist)
  .version          — current optimistic concurrency token
```

### Optimistic Concurrency

Each stream has a monotonically increasing version counter.  `append()` accepts
an `expected_version`; if the stored version differs, it raises
`ConcurrencyConflictError`.  Callers retry on conflict.

```python
try:
    await event_store.append(
        stream_id=f"order-{order.id}",
        events=order.uncommitted,
        expected_version=order.version,
    )
except ConcurrencyConflictError:
    order = await rebuild_aggregate(event_store, order.id)
    # ... re-apply the command
```

### Snapshots

Replaying long event streams (>500 events) at read time becomes expensive.
The `SnapshotStore` protocol stores a serialized aggregate state at a given
version.  `EventSourcedRepository.load()` loads the latest snapshot then
replays only events since that version.

```
SnapshotStore       — port: save(aggregate_id, snapshot, version)
                            load(aggregate_id) -> (snapshot, version) | None
```

Snapshot frequency is configurable per aggregate (default: every 100 events).

### Integration with `ProjectionStore`

Read models (projections) subscribe to the event stream via `EventPublisher`.
After `append()` succeeds, the repository calls `publisher.publish(events)`.
Projections are eventually consistent; they do **not** participate in the
event store transaction.

## Trade-offs

| Property | Event Sourcing | Standard Repository |
|---|---|---|
| Full audit history | Yes — every state change | No — only current state |
| Temporal queries | Yes | Only if implemented manually |
| Read performance | Replay cost (mitigated by snapshots) | Direct SELECT |
| Write complexity | Higher (optimistic locking, replay) | Lower |
| Schema evolution | Events are immutable; requires versioned upcasters | Standard migration |
| Debugging | Replay makes root-cause tracing easy | Harder without audit tables |

Event sourcing is opted in only when **audit history or replay** is a hard
requirement.  Simpler aggregates (e.g. `UserProfile`) use the standard
`SqlAlchemyRepository`.

## Schema Evolution

Because events are immutable once appended, changing the shape of a past event
requires an **upcaster** — a function that upgrades an old event schema to the
current schema at load time.  Upcasters are registered by `(event_type, version)`
and called transparently by `EventStore.load()`.

```python
@event_store.upcaster("OrderCreated", from_version=1)
def upgrade_v1_to_v2(raw: dict) -> dict:
    # v2 adds 'currency' field
    raw.setdefault("currency", "BRL")
    return raw
```

## Consequences

- Aggregates that use event sourcing **must** extend `EventSourcedAggregate`.
- The `SqlAlchemyEventStore` implementation appends all events for a given
  `expected_version` in a single `INSERT` with a unique constraint on
  `(stream_id, version)` — the database enforces the optimistic lock.
- Projections are rebuilt by replaying from version 0; rebuilding must be
  idempotent (use `ON CONFLICT DO NOTHING` in projection handlers).
- Events should be treated as a public API; breaking schema changes require
  major version bumps and upcasters for all stored events.
