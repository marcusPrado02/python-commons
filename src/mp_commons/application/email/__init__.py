"""Application email – ports and value objects."""

from mp_commons.application.email.in_memory import InMemoryEmailSender
from mp_commons.application.email.message import Attachment, EmailMessage
from mp_commons.application.email.sender import EmailSender

__all__ = [
    "Attachment",
    "EmailMessage",
    "EmailSender",
    "InMemoryEmailSender",
]
