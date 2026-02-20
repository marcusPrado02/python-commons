"""Resilience – BulkheadFullError."""
from __future__ import annotations
from mp_commons.kernel.errors import ApplicationError


class BulkheadFullError(ApplicationError):
    """Raised when the bulkhead is at capacity."""
    default_code = "bulkhead_full"


__all__ = ["BulkheadFullError"]
