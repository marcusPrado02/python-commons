"""Google Cloud Storage adapter — implements ObjectStore (A-04).

Mirrors the S3 :class:`~mp_commons.adapters.s3.object_store.S3ObjectStore`
API using ``google-cloud-storage`` with Application Default Credentials.

Usage::

    from mp_commons.adapters.gcs import GCSObjectStore

    store = GCSObjectStore(project="my-project", bucket_name="my-bucket")
    async with store:
        await store.put("path/to/file.txt", b"hello", "text/plain")
        data = await store.get("path/to/file.txt")
        url = await store.presigned_url("path/to/file.txt", expires_in=3600)
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _require_storage() -> Any:
    try:
        from google.cloud import storage  # type: ignore[import-untyped]

        return storage
    except ImportError as exc:
        raise ImportError(
            "google-cloud-storage is required for GCSObjectStore. "
            "Install it with: pip install 'google-cloud-storage>=2.14'"
        ) from exc


class GCSObjectStore:
    """Async ObjectStore backed by Google Cloud Storage.

    Wraps the synchronous GCS client in ``asyncio.get_event_loop().run_in_executor``
    so all operations are non-blocking.

    Parameters
    ----------
    bucket_name:
        GCS bucket name.
    project:
        GCP project ID.  Optional if the bucket is already accessible via ADC.
    credentials:
        Optional explicit credentials.
    """

    def __init__(
        self,
        bucket_name: str,
        project: str | None = None,
        *,
        credentials: Any = None,
    ) -> None:
        self._bucket_name = bucket_name
        self._project = project
        self._credentials = credentials
        self._client: Any = None
        self._bucket: Any = None

    async def __aenter__(self) -> GCSObjectStore:
        storage = _require_storage()
        kwargs: dict[str, Any] = {}
        if self._project:
            kwargs["project"] = self._project
        if self._credentials:
            kwargs["credentials"] = self._credentials
        self._client = storage.Client(**kwargs)
        self._bucket = self._client.bucket(self._bucket_name)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            self._bucket = None

    def _blob(self, key: str) -> Any:
        return self._bucket.blob(key)

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload *data* to blob *key*."""
        blob = self._blob(key)
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: blob.upload_from_string(data, content_type=content_type),
        )
        logger.debug("gcs.put key=%s size=%d", key, len(data))

    async def get(self, key: str) -> bytes:
        """Download blob *key*.  Raises :class:`KeyError` if not found."""
        blob = self._blob(key)
        try:
            return await asyncio.get_event_loop().run_in_executor(None, blob.download_as_bytes)
        except Exception as exc:
            exc_str = str(exc)
            if "NotFound" in type(exc).__name__ or "404" in exc_str or "No such object" in exc_str:
                raise KeyError(key) from exc
            raise

    async def delete(self, key: str) -> None:
        """Delete blob *key*.  No-op if not found."""
        blob = self._blob(key)
        try:
            await asyncio.get_event_loop().run_in_executor(None, blob.delete)
        except Exception as exc:
            exc_str = str(exc)
            if "NotFound" in type(exc).__name__ or "404" in exc_str or "No such object" in exc_str:
                return
            raise

    async def list(self, prefix: str = "") -> list[str]:
        """Return blob names under *prefix*."""
        blobs = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: list(self._client.list_blobs(self._bucket_name, prefix=prefix)),
        )
        return [b.name for b in blobs]

    async def presigned_url(self, key: str, *, expires_in: int = 3600) -> str:
        """Generate a signed URL valid for *expires_in* seconds.

        Requires that the credentials have permission to sign blobs
        (Service Account credentials or Workload Identity Federation).
        """
        blob = self._blob(key)
        expiration = timedelta(seconds=expires_in)
        url: str = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: blob.generate_signed_url(expiration=expiration, method="GET"),
        )
        return url


__all__ = ["GCSObjectStore"]
