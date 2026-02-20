# ADR-0006 — Result Type over Bare Exceptions in the Application Layer

**Status:** Accepted  
**Date:** 2026-01-15  
**Deciders:** Platform Team

---

## Context

Application layer command and query handlers need to communicate two categories
of failure to their callers:

1. **Expected domain failures** — e.g. "order not found", "insufficient funds",
   "duplicate idempotency key". These are part of the contract and callers
   must handle them explicitly.

2. **Unexpected infrastructure failures** — e.g. database connection dropped,
   timeout, serialisation error. These bubble up as exceptions and are handled
   by global error middleware.

Using bare `raise` for both categories makes it impossible for the type
checker to enforce that callers handle expected failures. A caller can always
forget to catch a `DomainError` subclass, and `mypy` will not warn.

## Decision

Application layer public APIs return `Result[T, E]` for operations that have
expected failure modes:

```python
from mp_commons.kernel.result import Result, Ok, Err

class PlaceOrderHandler(CommandHandler[PlaceOrderCommand, OrderId]):
    async def handle(
        self, cmd: PlaceOrderCommand
    ) -> Result[OrderId, DomainError]:
        if await self._orders.exists(cmd.order_id):
            return Err(DuplicateOrderError(cmd.order_id))
        order = Order.create(cmd)
        await self._orders.save(order)
        return Ok(order.id)
```

Callers pattern-match (or use `.unwrap()` / `.unwrap_or()`) to handle both
branches:

```python
result = await bus.dispatch(PlaceOrderCommand(...))
match result:
    case Ok(order_id):
        return {"order_id": str(order_id)}, 201
    case Err(DuplicateOrderError()):
        return {"error": "duplicate order"}, 409
```

### When *not* to use `Result`

- Infrastructure-only methods (repository `save`, `delete`) — raise on error.
- Unexpected failures always raise; `Result` is not a substitute for
  exception handling at the infrastructure boundary.

## Rationale

| Approach | Pro | Con |
|---|---|---|
| Bare `raise DomainError` | Familiar; less boilerplate | Type checker cannot enforce handling; callers silently propagate |
| `Result[T, E]` (chosen) | Explicit in type signature; `mypy` enforces handling | Slightly more verbose call sites |
| `Union[T, E]` | Type-safe | No semantic distinction between success/failure values |

## Consequences

- `mypy --strict` catches unhandled `Err` branches at the call site.
- Framework adapters (FastAPI route handlers) map `Err` variants to HTTP
  status codes in a single, tested `to_http_response(result)` helper.
- Tests can `assert result.is_ok()` or `assert result.unwrap_err() == ...`
  without re-raising.
- `Result` is defined in `mp_commons.kernel.result` with no third-party
  dependencies — usable in every layer.
