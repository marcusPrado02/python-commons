"""Azure Blob Storage adapter — implements ``ObjectStore`` (A-03).

Uses ``azure-storage-blob`` with managed-identity auth.  Mirrors the S3
:class:`~mp_commons.adapters.s3.object_store.S3ObjectStore` API exactly.

Usage::

    from mp_commons.adapters.azure_blob import AzureBlobObjectStore

    store = AzureBlobObjectStore(
        account_url="https://mystorageaccount.blob.core.windows.net",
        container_name="uploads",
    )
    async with store:
        await store.put("path/to/file.txt", b"hello world", "text/plain")
        data = await store.get("path/to/file.txt")
        url = await store.presigned_url("path/to/file.txt", expires_in=3600)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _require_blob() -> Any:
    try:
        from azure.storage.blob.aio import BlobServiceClient  # type: ignore[import-untyped]

        return BlobServiceClient
    except ImportError as exc:
        raise ImportError(
            "azure-storage-blob is required for AzureBlobObjectStore. "
            "Install it with: pip install 'azure-storage-blob>=12.19'"
        ) from exc


def _require_identity() -> Any:
    try:
        from azure.identity.aio import DefaultAzureCredential  # type: ignore[import-untyped]

        return DefaultAzureCredential
    except ImportError as exc:
        raise ImportError(
            "azure-identity is required for managed-identity auth. "
            "Install it with: pip install 'azure-identity>=1.15'"
        ) from exc


class AzureBlobObjectStore:
    """Async ``ObjectStore`` backed by Azure Blob Storage.

    Provides ``put``, ``get``, ``delete``, ``list``, and ``presigned_url``.

    Parameters
    ----------
    account_url:
        Full storage account URL, e.g.
        ``https://mystorageaccount.blob.core.windows.net``.
    container_name:
        Target blob container.
    connection_string:
        Optional connection string (takes precedence over managed identity).
    """

    def __init__(
        self,
        account_url: str,
        container_name: str,
        *,
        connection_string: str | None = None,
    ) -> None:
        self._account_url = account_url
        self._container_name = container_name
        self._connection_string = connection_string
        self._client: Any = None

    async def __aenter__(self) -> AzureBlobObjectStore:
        BlobServiceClient = _require_blob()
        if self._connection_string:
            self._client = BlobServiceClient.from_connection_string(self._connection_string)
        else:
            credential = _require_identity()()
            self._client = BlobServiceClient(self._account_url, credential=credential)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client is not None:
            await self._client.__aexit__(*_)
            self._client = None

    def _blob_client(self, key: str) -> Any:
        return self._client.get_blob_client(self._container_name, key)

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload *data* to blob *key*."""
        async with self._blob_client(key) as blob:
            await blob.upload_blob(
                data, overwrite=True, content_settings={"content_type": content_type}
            )
            logger.debug("azure_blob.put key=%s size=%d", key, len(data))

    async def get(self, key: str) -> bytes:
        """Download blob *key*.  Raises :class:`KeyError` if not found."""
        async with self._blob_client(key) as blob:
            try:
                stream = await blob.download_blob()
                return await stream.readall()
            except Exception as exc:
                if (
                    "BlobNotFound" in type(exc).__name__
                    or "404" in str(exc)
                    or "BlobNotFound" in str(exc)
                ):
                    raise KeyError(key) from exc
                raise

    async def delete(self, key: str) -> None:
        """Delete blob *key*.  No-op if not found."""
        async with self._blob_client(key) as blob:
            try:
                await blob.delete_blob()
            except Exception as exc:
                if (
                    "BlobNotFound" in type(exc).__name__
                    or "404" in str(exc)
                    or "BlobNotFound" in str(exc)
                ):
                    return
                raise

    async def list(self, prefix: str = "") -> list[str]:
        """Return a list of blob names under *prefix*."""
        container_client = self._client.get_container_client(self._container_name)
        keys: list[str] = []
        async for blob in container_client.list_blobs(name_starts_with=prefix):
            keys.append(blob.name)
        return keys

    async def presigned_url(self, key: str, *, expires_in: int = 3600) -> str:
        """Generate a SAS URL valid for *expires_in* seconds.

        Requires that the credentials have permission to generate SAS tokens
        (e.g. ``Storage Blob Delegator`` role for managed identity).
        """
        from azure.storage.blob import (  # type: ignore[import-untyped]
            BlobSasPermissions,
            generate_blob_sas,
        )

        expiry = datetime.now(UTC) + timedelta(seconds=expires_in)
        # For user delegation SAS with managed identity, we need a user delegation key
        # Synchronous key fetch via sync client is simpler here
        sas_token = generate_blob_sas(
            account_name=self._client.account_name,
            container_name=self._container_name,
            blob_name=key,
            account_key=self._client.credential.account_key
            if hasattr(self._client.credential, "account_key")
            else None,
            permission=BlobSasPermissions(read=True),
            expiry=expiry,
        )
        return f"{self._account_url}/{self._container_name}/{key}?{sas_token}"


__all__ = ["AzureBlobObjectStore"]
