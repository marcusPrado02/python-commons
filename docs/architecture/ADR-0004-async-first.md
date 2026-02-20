# ADR-0004 — Async-First Design

**Status:** Accepted  
**Date:** 2026-01-15  
**Deciders:** Platform Team

---

## Context

Modern Python microservices handle I/O-bound workloads (database queries,
HTTP requests, message publishing) that benefit from cooperative concurrency
via `asyncio`. Offering synchronous wrappers as the primary API forces every
caller to either block an event loop thread or maintain two separate code
paths.

## Decision

All I/O-bound operations in `mp-commons` are **async-first**:

1. Every port method that touches I/O is declared with `async def`.
2. Application services (`CommandHandler`, `QueryHandler`) are `async def`.
3. Middleware pipeline steps (`CommandMiddleware`, `QueryMiddleware`) are
   `async def`.
4. Resilience primitives (`RetryPolicy`, `CircuitBreaker`) expose
   `execute_async(fn)` as the primary entry point.

Synchronous variants are **opt-in wrappers**, not defaults:

```python
# Async (primary)
result = await command_bus.dispatch(cmd)

# Sync wrapper (opt-in, for scripts / legacy callers)
import asyncio
result = asyncio.run(command_bus.dispatch(cmd))
```

`mp-commons` does **not** ship sync wrappers itself; callers that need them
are expected to use `asyncio.run()` or a framework adapter.

## Rationale

| Option | Pros | Cons |
|---|---|---|
| Sync-first | Simpler for scripts | Blocks event loop; requires `run_in_executor` in async contexts |
| Async-first (chosen) | Composable in any async framework; zero overhead in sync contexts via `asyncio.run()` | Slightly more boilerplate in simple scripts |
| Dual API | Maximum flexibility | Double the surface area to test and maintain |

## Consequences

- Services using FastAPI, aiohttp, or raw `asyncio` can `await` library
  calls directly without thread-pool overhead.
- Unit tests for application services follow the same `asyncio.run()` or
  `pytest-asyncio` pattern — no sync shim needed.
- Blocking adapters (e.g. a sync ORM) must be wrapped in
  `asyncio.to_thread(...)` inside the adapter, keeping the port interface clean.
- Library code never calls `asyncio.run()` internally; that is the caller's
  responsibility.
