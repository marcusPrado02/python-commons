"""Application cache – CacheKey builder."""
from __future__ import annotations

import hashlib
import json

__all__ = ["CacheKey"]


class CacheKey:
    """Factory for deterministic cache key strings."""

    @staticmethod
    def for_resource(resource_type: str, resource_id: str | int) -> str:
        return f"{resource_type}:{resource_id}"

    @staticmethod
    def for_query(query_type: str, **kwargs: object) -> str:
        # deterministic: sort kwargs, JSON-encode, SHA-256 first 16 hex chars
        canonical = json.dumps(kwargs, sort_keys=True, default=str)
        digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        return f"query:{query_type}:{digest}"
