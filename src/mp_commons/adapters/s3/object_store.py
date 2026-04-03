"""Object-store port, S3 implementation, and in-memory fake."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


def _require_aiobotocore() -> Any:
    try:
        import aiobotocore.session  # type: ignore[import-untyped]

        return aiobotocore.session
    except ImportError as exc:
        raise ImportError(
            "aiobotocore is required for S3ObjectStore. "
            "Install it with: pip install 'aiobotocore>=2.7'"
        ) from exc


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ObjectStore(Protocol):
    """Kernel port for binary object storage."""

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """Store *data* under *key*."""
        ...

    async def get(self, key: str) -> bytes:
        """Retrieve data for *key*.  Raises :class:`KeyError` if absent."""
        ...

    async def delete(self, key: str) -> None:
        """Delete *key*.  No-op if absent."""
        ...

    async def exists(self, key: str) -> bool:
        """Return ``True`` if *key* exists."""
        ...

    async def list_keys(self, prefix: str = "") -> list[str]:
        """Return all keys with the given prefix."""
        ...


# ---------------------------------------------------------------------------
# In-memory fake (always available)
# ---------------------------------------------------------------------------


class InMemoryObjectStore:
    """Dict-backed fake :class:`ObjectStore` for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}
        self._metadata: dict[str, str] = {}

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        self._store[key] = data
        self._metadata[key] = content_type

    async def get(self, key: str) -> bytes:
        if key not in self._store:
            raise KeyError(key)
        return self._store[key]

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._metadata.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._store

    async def list_keys(self, prefix: str = "") -> list[str]:
        return [k for k in self._store if k.startswith(prefix)]


# ---------------------------------------------------------------------------
# S3 implementation (requires aiobotocore)
# ---------------------------------------------------------------------------


class S3ObjectStore:
    """Bucket-scoped S3 object store backed by aiobotocore.

    Parameters
    ----------
    bucket:
        S3 bucket name.
    region:
        AWS region (default ``us-east-1``).
    endpoint_url:
        Override endpoint, useful for MinIO / LocalStack.
    **session_kwargs:
        Extra kwargs forwarded to :func:`aiobotocore.get_session`.
    """

    def __init__(
        self,
        bucket: str,
        *,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        **session_kwargs: Any,
    ) -> None:
        _require_aiobotocore()
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url
        self._session_kwargs = session_kwargs

    def _client_context(self) -> Any:
        import aiobotocore.session as _session  # type: ignore[import-untyped]

        session = _session.get_session()
        kwargs: dict[str, Any] = {"region_name": self._region}
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        kwargs.update(self._session_kwargs)
        return session.create_client("s3", **kwargs)

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        async with self._client_context() as s3:
            await s3.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    async def get(self, key: str) -> bytes:
        async with self._client_context() as s3:
            try:
                resp = await s3.get_object(Bucket=self._bucket, Key=key)
                return await resp["Body"].read()
            except Exception as exc:
                if "NoSuchKey" in type(exc).__name__ or "NoSuchKey" in str(exc):
                    raise KeyError(key) from exc
                raise

    async def delete(self, key: str) -> None:
        async with self._client_context() as s3:
            await s3.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        async with self._client_context() as s3:
            try:
                await s3.head_object(Bucket=self._bucket, Key=key)
                return True
            except Exception:
                return False

    async def list_keys(self, prefix: str = "") -> list[str]:
        async with self._client_context() as s3:
            resp = await s3.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
            return [obj["Key"] for obj in resp.get("Contents", [])]


# ---------------------------------------------------------------------------
# Presigned URL generator
# ---------------------------------------------------------------------------


class S3PresignedUrlGenerator:
    """Generate pre-signed S3 URLs for GET and PUT operations."""

    def __init__(
        self,
        bucket: str,
        *,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        **session_kwargs: Any,
    ) -> None:
        _require_aiobotocore()
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url
        self._session_kwargs = session_kwargs

    def _client_context(self) -> Any:
        import aiobotocore.session as _session  # type: ignore[import-untyped]

        session = _session.get_session()
        kwargs: dict[str, Any] = {"region_name": self._region}
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        kwargs.update(self._session_kwargs)
        return session.create_client("s3", **kwargs)

    async def presign_get(self, key: str, expires_in: int = 3600) -> str:
        """Return a pre-signed GET URL valid for *expires_in* seconds."""
        async with self._client_context() as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )

    async def presign_put(
        self, key: str, expires_in: int = 3600, content_type: str = "application/octet-stream"
    ) -> str:
        """Return a pre-signed PUT URL valid for *expires_in* seconds."""
        async with self._client_context() as s3:
            return await s3.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=expires_in,
            )


__all__ = [
    "InMemoryObjectStore",
    "ObjectStore",
    "S3ObjectStore",
    "S3PresignedUrlGenerator",
]
