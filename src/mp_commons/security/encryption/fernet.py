from __future__ import annotations

import os
from typing import Protocol

from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

__all__ = [
    "AesGcmEncryptionProvider",
    "EncryptionProvider",
    "FernetEncryptionProvider",
]


class EncryptionProvider(Protocol):
    """Stateless encryption/decryption contract."""

    def encrypt(self, plaintext: bytes) -> bytes: ...
    def decrypt(self, ciphertext: bytes) -> bytes: ...


class FernetEncryptionProvider:
    """Fernet symmetric encryption; supports key rotation via MultiFernet list."""

    def __init__(self, keys: list[bytes | str]) -> None:
        fernet_keys = [Fernet(k if isinstance(k, bytes) else k.encode()) for k in keys]
        self._multi = MultiFernet(fernet_keys)

    @classmethod
    def generate_key(cls) -> bytes:
        return Fernet.generate_key()

    def encrypt(self, plaintext: bytes) -> bytes:
        return self._multi.encrypt(plaintext)

    def decrypt(self, ciphertext: bytes) -> bytes:
        return self._multi.decrypt(ciphertext)


class AesGcmEncryptionProvider:
    """AES-256-GCM authenticated encryption. Nonce prepended to ciphertext."""

    _NONCE_LEN = 12

    def __init__(self, key: bytes) -> None:
        if len(key) not in (16, 24, 32):
            raise ValueError("AES key must be 16, 24 or 32 bytes")
        self._aesgcm = AESGCM(key)

    @classmethod
    def generate_key(cls) -> bytes:
        return os.urandom(32)

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(self._NONCE_LEN)
        ct = self._aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ct

    def decrypt(self, ciphertext: bytes) -> bytes:
        nonce = ciphertext[: self._NONCE_LEN]
        ct = ciphertext[self._NONCE_LEN :]
        return self._aesgcm.decrypt(nonce, ct, None)
