"""FastAPI adapter – middleware, exception mapper, health/metrics routers, deps."""
from mp_commons.adapters.fastapi.deps import FastAPIPaginationDep, error_responses
from mp_commons.adapters.fastapi.exception_mapper import FastAPIExceptionMapper
from mp_commons.adapters.fastapi.middleware import (
    FastAPICorrelationIdMiddleware,
    FastAPIMetricsMiddleware,
    FastAPIRateLimitMiddleware,
    FastAPIRequestContextMiddleware,
    FastAPISecurityMiddleware,
    FastAPITenantMiddleware,
)
from mp_commons.adapters.fastapi.routers import FastAPIHealthRouter, FastAPIMetricsRouter

__all__ = [
    "FastAPICorrelationIdMiddleware",
    "FastAPIExceptionMapper",
    "FastAPIHealthRouter",
    "FastAPIMetricsMiddleware",
    "FastAPIMetricsRouter",
    "FastAPIPaginationDep",
    "FastAPIRateLimitMiddleware",
    "FastAPIRequestContextMiddleware",
    "FastAPISecurityMiddleware",
    "FastAPITenantMiddleware",
    "error_responses",
]
