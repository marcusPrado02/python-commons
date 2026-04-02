"""S3 / object-store adapter.

Requires ``aiobotocore>=2.7``.  The :class:`InMemoryObjectStore` is always
available without any extra dependencies.
"""

from __future__ import annotations

from mp_commons.adapters.s3.object_store import (
    InMemoryObjectStore,
    ObjectStore,
    S3ObjectStore,
    S3PresignedUrlGenerator,
)

__all__ = [
    "InMemoryObjectStore",
    "ObjectStore",
    "S3ObjectStore",
    "S3PresignedUrlGenerator",
]
