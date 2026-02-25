"""Application files – FileUploadService and ObjectStore protocol."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from mp_commons.application.files.upload import UploadedFile
from mp_commons.application.files.validator import FileValidator, FileValidationError

__all__ = [
    "FileUploadService",
    "FileUploadedEvent",
    "InMemoryObjectStore",
    "ObjectStore",
]


@dataclass(frozen=True)
class FileUploadedEvent:
    """Domain event emitted after a successful file upload."""

    destination_key: str
    url: str
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str


@runtime_checkable
class ObjectStore(Protocol):
    """Port: stores binary objects and returns their public URL/key."""

    async def put(self, key: str, data: bytes, content_type: str) -> str:
        """Store *data* at *key*; return the canonical URL or storage key."""
        ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...


class InMemoryObjectStore:
    """Fake ObjectStore for unit tests."""

    def __init__(self, base_url: str = "https://storage.example.com") -> None:
        self._base_url = base_url.rstrip("/")
        self._store: dict[str, bytes] = {}
        self._content_types: dict[str, str] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> str:
        self._store[key] = data
        self._content_types[key] = content_type
        return f"{self._base_url}/{key}"

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._content_types.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._store

    def get(self, key: str) -> bytes | None:
        return self._store.get(key)


class FileUploadService:
    """Uploads files via an ObjectStore, optionally validating first."""

    def __init__(
        self,
        store: ObjectStore,
        validator: FileValidator | None = None,
    ) -> None:
        self._store = store
        self._validator = validator
        self.events: list[FileUploadedEvent] = []

    async def upload(self, file: UploadedFile, destination_key: str) -> str:
        """Validate (if validator provided), store file, emit event, return URL."""
        if self._validator is not None:
            self._validator.validate_or_raise(file)

        if isinstance(file.data, bytes):
            data = file.data
        else:
            chunks = []
            async for chunk in file.data:
                chunks.append(chunk)
            data = b"".join(chunks)

        url = await self._store.put(destination_key, data, file.content_type)
        event = FileUploadedEvent(
            destination_key=destination_key,
            url=url,
            filename=file.filename,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            checksum_sha256=file.checksum_sha256,
        )
        self.events.append(event)
        return url
