# ADR-0007 — Multi-Tenancy: TenantContext + TenantFilter

**Status:** Accepted
**Date:** 2026-02-01
**Deciders:** Platform Team

---

## Context

Several services built on `mp-commons` operate in a multi-tenant SaaS model
where a single deployment serves many independent customers ("tenants").
Data isolation between tenants is a critical security and compliance requirement.

Two common approaches exist in the literature:

1. **Database-per-tenant** — strongest isolation but operationally expensive
   (N databases, N connection pools, N migration runs per deploy).
2. **Row-level isolation** — all tenants share tables; a discriminator column
   (`tenant_id`) filters every query.

Within row-level isolation there are further sub-approaches:
- **Application-enforced filtering** — ORM repositories apply a `WHERE tenant_id = ?`
  clause on every query; the application is responsible for correctness.
- **Database-enforced row-level security (RLS)** — PostgreSQL RLS policies
  automatically filter rows based on a session variable.

## Decision

We adopt **application-enforced row-level isolation** using two primitives:

### `TenantContext` (context variable)
A `contextvars.ContextVar` holding the active `TenantId` for the current
async execution context.  Middleware populates it from the `X-Tenant-ID` HTTP
header (or JWT `tenant_id` claim) at the boundary of each request.

```python
# FastAPI middleware (automatic population)
app.add_middleware(FastAPITenantMiddleware)

# Manual population (e.g. background workers)
TenantContext.set("tenant-abc")
```

### `TenantFilter` (SQLAlchemy mixin)
A `where()` clause builder that injects `Model.tenant_id == TenantContext.get()`
into every `SELECT`, `UPDATE`, and `DELETE` statement executed through a
`TenantAwareSqlAlchemyRepository`.

```python
class OrderRepository(TenantAwareSqlAlchemyRepository[Order]):
    pass  # tenant_id filter applied automatically
```

### `TenantIsolationValidator` (test helper)
A test utility that wraps a real repository and asserts that every returned
entity belongs to the active tenant.  This catches cross-tenant data leaks in
integration tests without requiring end-to-end traffic.

## Trade-offs

| Property | This approach | RLS | DB-per-tenant |
|---|---|---|---|
| Data isolation | Application-enforced | Database-enforced | Physical |
| Correctness risk | Forgot `WHERE` in custom query | Low | Low |
| Ops complexity | Low | Medium | High |
| Connection pool cost | O(1) | O(1) | O(N tenants) |
| Migration cost | 1 run | 1 run | N runs |
| Cross-tenant analytics | Easy (remove filter) | Hard (superuser) | Very hard |

Application-enforced filtering is chosen because:
- The team can audit all query paths through the `TenantAwareSqlAlchemyRepository` base class.
- `TenantIsolationValidator` provides automated test coverage as a safety net.
- Services with compliance requirements (e.g. HIPAA, GDPR) that need
  stronger isolation can adopt RLS per-service by overriding the repository.

## How to Opt Out

A repository that intentionally operates across tenants (e.g. a billing
aggregation job) should extend the base `SqlAlchemyRepository` directly rather
than `TenantAwareSqlAlchemyRepository`:

```python
class CrossTenantInvoiceReport(SqlAlchemyRepository[Invoice]):
    # No tenant_id filter — must document why this is safe
    ...
```

Such repositories should be clearly named and reviewed for data exposure risk.

## Consequences

- All repositories in tenant-scoped services **must** extend `TenantAwareSqlAlchemyRepository`.
- `FastAPITenantMiddleware` **must** be added to every tenant-scoped FastAPI app.
- Background workers **must** explicitly call `TenantContext.set(tenant_id)` before dispatching commands.
- Integration tests covering multi-tenant paths **must** use `TenantIsolationValidator`.
