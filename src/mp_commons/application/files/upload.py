"""Application files – UploadedFile value object."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import AsyncIterator

__all__ = ["UploadedFile"]


@dataclass
class UploadedFile:
    """Represents a file received for upload."""

    filename: str
    content_type: str
    size_bytes: int
    data: bytes | AsyncIterator[bytes]
    checksum_sha256: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.data, bytes) and not self.checksum_sha256:
            self.checksum_sha256 = hashlib.sha256(self.data).hexdigest()

    @classmethod
    def from_bytes(cls, filename: str, content_type: str, data: bytes) -> "UploadedFile":
        return cls(
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            data=data,
        )
