# ADR-0003 — Ports and Adapters (Hexagonal Architecture)

**Status:** Accepted  
**Date:** 2026-01-15  
**Deciders:** Platform Team

---

## Context

`mp-commons` is consumed by multiple microservices, each of which may use
different persistence engines (PostgreSQL, MongoDB, Redis), messaging brokers
(RabbitMQ, Kafka, Azure Service Bus), and web frameworks (FastAPI, Django,
plain asyncio).

If the library bundled concrete implementations alongside the abstractions,
every service would be forced to install — and be exposed to security
vulnerabilities of — frameworks they do not use.

## Decision

We apply the **Ports and Adapters** pattern (also called Hexagonal
Architecture):

| Concept | Location in `mp-commons` |
|---|---|
| **Port** (abstraction) | `kernel.*` and `application.*` — pure Python `Protocol` or `ABC`; zero third-party imports |
| **Adapter** (implementation) | `adapters.*` — concrete classes that depend on an optional extra |

Rules:

1. **Ports live in `kernel.*` or `application.*`.**  
   A port is a `typing.Protocol` (structural) or an `abc.ABC` (nominal).  
   It imports nothing outside stdlib.

2. **Adapters live in `adapters.*`.**  
   An adapter provides a concrete implementation of a port.  
   Its third-party imports are **lazy-guarded**:

   ```python
   def _require_sqlalchemy() -> None:
       try:
           import sqlalchemy  # noqa: F401
       except ImportError:
           raise ImportError(
               "SQLAlchemy is required. "
               "Install it with: pip install mp-commons[sqlalchemy]"
           ) from None
   ```

3. **Application services depend only on ports**, never on adapters.  
   Wiring (injecting the adapter into the service) happens at the
   composition root — typically the service's `main.py` or a DI container.

4. **Testing doubles live in `testing.*`.**  
   `InMemoryOutboxRepository`, `FakeClock`, etc. implement the same ports
   and can be injected in unit tests without any infrastructure running.

## Consequences

- A service can start with zero adapters and add them incrementally.
- Swapping a persistence engine affects only the adapter, never the domain
  or application logic.
- All adapters are optional extras; `pip install mp-commons` installs only
  the port definitions.
- The same port can have multiple adapters
  (e.g. `SQLAlchemyOutboxStore` and `MongoOutboxStore`).

## Examples

```python
# Port (kernel layer)
from mp_commons.kernel.outbox import OutboxRepository

# Adapter (adapters layer — optional sqlalchemy extra)
from mp_commons.adapters.sqlalchemy.outbox import SQLAlchemyOutboxStore

# Testing double (testing layer)
from mp_commons.testing.fakes import InMemoryOutboxRepository

# Composition root
repo: OutboxRepository = SQLAlchemyOutboxStore(session_factory)
service = OrderService(outbox=repo)
```
