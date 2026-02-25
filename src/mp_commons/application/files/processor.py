"""Application files – ImageResizer (optional Pillow extra) and AntivirusScanner."""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

__all__ = ["AntivirusScanner", "ImageResizer", "ScanResult"]


def _require_pillow() -> Any:  # pragma: no cover
    try:
        from PIL import Image  # noqa: PLC0415
        return Image
    except ImportError as exc:
        raise ImportError(
            "Pillow is required for ImageResizer. "
            "Install it with: pip install Pillow"
        ) from exc


class ImageResizer:
    """Resizes PNG/JPEG images using Pillow."""

    async def resize(self, data: bytes, width: int, height: int, *, fmt: str = "JPEG") -> bytes:
        Image = _require_pillow()  # pragma: no cover
        img = Image.open(io.BytesIO(data))  # pragma: no cover
        img = img.resize((width, height), Image.LANCZOS)  # pragma: no cover
        buf = io.BytesIO()  # pragma: no cover
        img.save(buf, format=fmt)  # pragma: no cover
        return buf.getvalue()  # pragma: no cover


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    threat_name: str | None = None
    detail: str | None = None


@runtime_checkable
class AntivirusScanner(Protocol):
    """Port: scan binary data for malware."""

    async def scan(self, data: bytes) -> ScanResult: ...
