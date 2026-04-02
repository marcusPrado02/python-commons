"""Certificate loading, expiry checking, and mTLS helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import ssl
from typing import Any

__all__ = [
    "CertificateExpiryChecker",
    "CertificateLoader",
    "MtlsHttpxClient",
]


class CertificateLoader:
    """Loads PEM or PKCS#12 certificates into ssl.SSLContext objects."""

    @staticmethod
    def from_pem(
        certfile: str | Path,
        keyfile: str | Path | None = None,
        cafile: str | Path | None = None,
        *,
        purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH,
    ) -> ssl.SSLContext:
        """Load a PEM certificate (and optionally a key) into a new SSLContext."""
        ctx = ssl.SSLContext(
            ssl.PROTOCOL_TLS_CLIENT
            if purpose == ssl.Purpose.SERVER_AUTH
            else ssl.PROTOCOL_TLS_SERVER
        )
        ctx.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile) if keyfile else None)
        if cafile:
            ctx.load_verify_locations(cafile=str(cafile))
        else:
            ctx.load_default_certs(purpose)
        return ctx

    @staticmethod
    def from_pkcs12(
        pkcs12_path: str | Path,
        password: str | bytes | None = None,
        *,
        purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH,
    ) -> ssl.SSLContext:
        """Load a PKCS#12 bundle (.p12 / .pfx) into a new SSLContext."""
        try:
            from cryptography.hazmat.primitives.serialization import (
                Encoding,
                NoEncryption,
                PrivateFormat,
            )
            from cryptography.hazmat.primitives.serialization.pkcs12 import load_pkcs12
        except ImportError as exc:  # pragma: no cover
            raise ImportError("pip install cryptography") from exc

        data = Path(pkcs12_path).read_bytes()
        pwd = password.encode() if isinstance(password, str) else password
        p12 = load_pkcs12(data, pwd)

        import os
        import tempfile

        ctx = ssl.SSLContext(
            ssl.PROTOCOL_TLS_CLIENT
            if purpose == ssl.Purpose.SERVER_AUTH
            else ssl.PROTOCOL_TLS_SERVER
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cf:
            cert_pem = p12.cert.certificate.public_bytes(Encoding.PEM)
            key_pem = p12.key.private_bytes(
                Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
            )
            cf.write(cert_pem + key_pem)
            tmp_path = cf.name
        try:
            ctx.load_cert_chain(tmp_path)
        finally:
            os.unlink(tmp_path)
        return ctx

    @staticmethod
    def create_client_context(
        certfile: str | Path,
        keyfile: str | Path,
        cafile: str | Path,
    ) -> ssl.SSLContext:
        """Mutual TLS: client presents cert, verifies server against cafile."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))
        ctx.load_verify_locations(cafile=str(cafile))
        return ctx


class MtlsHttpxClient:
    """httpx.AsyncClient pre-wired for mTLS."""

    def __init__(self, ssl_context: ssl.SSLContext) -> None:
        self._ssl_context = ssl_context

    def build(self) -> Any:
        """Return an httpx.AsyncClient configured with the mTLS SSLContext."""
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise ImportError("pip install httpx") from exc
        return httpx.AsyncClient(verify=self._ssl_context)

    @classmethod
    def from_pem(
        cls,
        certfile: str | Path,
        keyfile: str | Path,
        cafile: str | Path,
    ) -> MtlsHttpxClient:
        ctx = CertificateLoader.create_client_context(certfile, keyfile, cafile)
        return cls(ctx)


class CertificateExpiryChecker:
    """Utility for checking certificate expiry dates."""

    @staticmethod
    def days_until_expiry(pem_path: str | Path) -> int:
        """Return the number of days until the first certificate in pem_path expires.

        Returns a negative number if the certificate has already expired.
        """
        try:
            from cryptography import x509
        except ImportError as exc:  # pragma: no cover
            raise ImportError("pip install cryptography") from exc

        pem_data = Path(pem_path).read_bytes()
        cert = x509.load_pem_x509_certificate(pem_data)
        expiry = cert.not_valid_after_utc
        delta = expiry - datetime.now(UTC)
        return delta.days

    @staticmethod
    def is_expiring_soon(pem_path: str | Path, threshold_days: int = 30) -> bool:
        return CertificateExpiryChecker.days_until_expiry(pem_path) < threshold_days
