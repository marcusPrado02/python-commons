"""Certificate fingerprint pinning."""

from __future__ import annotations

import hashlib

__all__ = [
    "CertPinningError",
    "CertificatePinner",
]


class CertPinningError(Exception):
    """Raised when a certificate fingerprint does not match the pinned set."""


class CertificatePinner:
    """Pins expected SHA-256 fingerprints for specific hostnames."""

    def __init__(self) -> None:
        self._pins: dict[str, set[str]] = {}

    def pin(self, host: str, expected_fingerprints: list[str]) -> None:
        """Associate one or more expected hex fingerprints with *host*."""
        normalised = {fp.lower().replace(":", "") for fp in expected_fingerprints}
        self._pins.setdefault(host, set()).update(normalised)

    def verify(self, host: str, cert_der: bytes) -> bool:
        """Return True if cert_der's SHA-256 fingerprint matches a pinned value.

        Raises ``CertPinningError`` on mismatch.
        Raises ``KeyError`` if *host* has no pinned fingerprints — always True.
        """
        if host not in self._pins:
            return True
        fp = hashlib.sha256(cert_der).hexdigest().lower()
        if fp in self._pins[host]:
            return True
        raise CertPinningError(
            f"Certificate fingerprint {fp!r} for host {host!r} does not match pinned values."
        )

    def pinned_hosts(self) -> list[str]:
        return list(self._pins)
