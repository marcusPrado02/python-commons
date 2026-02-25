"""Application email – EmailMessage and Attachment value objects."""
from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Attachment", "EmailMessage"]


@dataclass(frozen=True)
class Attachment:
    """A file attachment for an email."""

    filename: str
    content_type: str
    data: bytes

    def __repr__(self) -> str:  # pragma: no cover
        return f"Attachment(filename={self.filename!r}, content_type={self.content_type!r}, size={len(self.data)})"


@dataclass
class EmailMessage:
    """A fully-resolved email message ready to be sent."""

    to: list[str]
    subject: str
    html_body: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    text_body: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
    reply_to: str | None = None

    def all_recipients(self) -> list[str]:
        """Return combined to + cc + bcc recipient list."""
        return self.to + self.cc + self.bcc
