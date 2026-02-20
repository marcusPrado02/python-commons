# ADR-0001 — Kernel Boundary Rules

**Status:** Accepted  
**Date:** 2026-01-01  
**Deciders:** Platform Team

---

## Context

`mp-commons` is imported by multiple services. If the kernel leaks framework
dependencies (FastAPI, SQLAlchemy, Redis, …) every service that imports the
library transitively pulls those dependencies regardless of need.

## Decision

The `mp_commons.kernel` package and all sub-packages **must have zero
runtime imports** of any third-party library. Allowed stdlib imports only.

Enforced rules:

| Layer | May import |
|---|---|
| `kernel.*` | stdlib only |
| `application.*` | `kernel.*` + stdlib |
| `resilience.*` | `kernel.*` + `application.*` + stdlib |
| `observability.*` | `kernel.*` + stdlib |
| `config.*` | `kernel.*` + stdlib |
| `adapters.*` | anything (lazy-guarded) |
| `testing.*` | anything |

Adapters must guard third-party imports behind a `_require_*()` helper that
raises `ImportError` with a human-readable install hint when the optional
extra is absent.

## Consequences

- Services can `pip install mp-commons` with no extras and get the full
  kernel, application, resilience, observability, and config layers.
- Framework bindings (FastAPI, SQLAlchemy, …) are installed only when the
  corresponding extra is specified: `mp-commons[fastapi,sqlalchemy]`.
- A lint rule (`no-third-party-imports-in-kernel`) is enforced in CI via
  `ruff` import-boundary checks and a custom `mypy` plugin stub.
