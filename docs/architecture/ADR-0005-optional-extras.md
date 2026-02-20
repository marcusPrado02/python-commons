# ADR-0005 — Optional Extras and Import-Time Failure Hints

**Status:** Accepted  
**Date:** 2026-01-15  
**Deciders:** Platform Team

---

## Context

`mp-commons` provides adapters for multiple third-party libraries (SQLAlchemy,
Redis, FastAPI, Motor, httpx, …). A service that only needs the kernel and a
single adapter should not be forced to install the full dependency tree.

At the same time, if a service imports an adapter without having installed the
required extra, it should receive a clear, actionable error message — not a
bare `ModuleNotFoundError` deep inside a transitive import.

## Decision

Adapter dependencies are declared as **optional extras** in `pyproject.toml`:

```toml
[project.optional-dependencies]
sqlalchemy  = ["sqlalchemy>=2.0", "alembic>=1.13"]
redis       = ["redis>=5.0"]
fastapi     = ["fastapi>=0.110", "httpx>=0.27"]
mongodb     = ["motor>=3.3"]
all-adapters = [
    "mp-commons[sqlalchemy]",
    "mp-commons[redis]",
    "mp-commons[fastapi]",
    "mp-commons[mongodb]",
]
```

Every adapter module guards its third-party import with a helper that raises
`ImportError` with an install hint:

```python
def _require_redis() -> None:
    try:
        import redis  # noqa: F401
    except ImportError:
        raise ImportError(
            "The redis adapter requires the redis extra.\n"
            "Install it with:  pip install mp-commons[redis]"
        ) from None
```

Rules:

1. The guard is called **lazily** — only when the adapter class is
   instantiated or a method is invoked, not at module import time.
2. The error message **always includes the exact `pip install` command**.
3. The base `mp-commons` package (no extras) must be importable with zero
   third-party packages installed.

## Consequences

- `pip install mp-commons` installs <5 MB with no compiled extensions.
- `pip install mp-commons[sqlalchemy]` adds only the SQLAlchemy stack.
- Misconfigured environments fail loudly with a one-line fix,
  rather than a confusing `AttributeError` or `ImportError` without context.
- CI matrix can test each extra in isolation, catching accidental cross-extra
  import leaks.
