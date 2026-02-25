"""Application webhooks – HMAC-SHA256 request signing."""
from __future__ import annotations

import hashlib
import hmac

__all__ = ["WebhookSigner"]


class WebhookSigner:
    """Signs and verifies webhook payloads using HMAC-SHA256."""

    ALG = "sha256"

    @classmethod
    def sign(cls, payload: bytes, secret: str) -> str:
        """Return a signature string of the form ``sha256=<hexdigest>``."""
        mac = hmac.new(secret.encode(), payload, hashlib.sha256)
        return f"{cls.ALG}={mac.hexdigest()}"

    @classmethod
    def verify(cls, payload: bytes, secret: str, signature: str) -> bool:
        """Verify *signature* using constant-time comparison."""
        expected = cls.sign(payload, secret)
        return hmac.compare_digest(expected.encode(), signature.encode())
