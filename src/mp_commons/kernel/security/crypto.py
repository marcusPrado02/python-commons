"""Kernel security – PasswordHasher, CryptoProvider ports."""
from __future__ import annotations

import abc


class PasswordHasher(abc.ABC):
    """Port: one-way password hashing."""

    @abc.abstractmethod
    def hash(self, password: str) -> str: ...

    @abc.abstractmethod
    def verify(self, password: str, hashed: str) -> bool: ...


class CryptoProvider(abc.ABC):
    """Port: symmetric encryption / decryption."""

    @abc.abstractmethod
    def encrypt(self, plaintext: bytes, *, key_id: str | None = None) -> bytes: ...

    @abc.abstractmethod
    def decrypt(self, ciphertext: bytes, *, key_id: str | None = None) -> bytes: ...


__all__ = ["CryptoProvider", "PasswordHasher"]
