"""Zero-downtime API key hash algorithm upgrade — bcrypt → argon2 (S-05).

:class:`ApiKeyHashUpgrade` wraps an :class:`ApiKeyVerifier` and transparently
upgrades stored ``bcrypt`` hashes to ``argon2id`` the next time a key is
successfully verified.  This allows a gradual, rolling migration with no
downtime or forced re-enrollment.

Usage::

    from mp_commons.security.apikeys.hash_upgrade import ApiKeyHashUpgrade

    upgrader = ApiKeyHashUpgrade(store=my_api_key_store)
    key_record = await upgrader.verify_and_upgrade(raw_key)
    if key_record is None:
        raise Unauthorized()
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import bcrypt

from mp_commons.security.apikeys.generator import ApiKey, ApiKeyStore

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_BCRYPT_PREFIX = b"$2"
_ARGON2_PREFIX = b"$argon2"


def _is_bcrypt(key_hash: bytes) -> bool:
    return key_hash.startswith(_BCRYPT_PREFIX)


def _is_argon2(key_hash: bytes) -> bool:
    return key_hash.startswith(_ARGON2_PREFIX)


def _require_argon2() -> Any:
    try:
        import argon2  # type: ignore[import-untyped]
        return argon2
    except ImportError as exc:
        raise ImportError(
            "Install 'mp-commons[argon2]' or 'argon2-cffi' to use ApiKeyHashUpgrade"
        ) from exc


from typing import Any


class ApiKeyHashUpgrade:
    """Transparent bcrypt → argon2id hash migration on each successful verify.

    On every successful verification the stored hash is inspected.  If it is
    a ``bcrypt`` hash, the raw key is re-hashed with ``argon2id`` and the
    record is updated in the store — a single ``store.save()`` call replaces
    the hash in place.

    Parameters
    ----------
    store:
        The :class:`ApiKeyStore` to read and update records.
    argon2_time_cost:
        Argon2 time cost parameter (iterations).
    argon2_memory_cost:
        Argon2 memory cost in KiB.
    argon2_parallelism:
        Argon2 parallelism factor (number of threads).
    """

    def __init__(
        self,
        store: ApiKeyStore,
        argon2_time_cost: int = 2,
        argon2_memory_cost: int = 65536,
        argon2_parallelism: int = 2,
    ) -> None:
        self._store = store
        self._time_cost = argon2_time_cost
        self._memory_cost = argon2_memory_cost
        self._parallelism = argon2_parallelism

        # Lazily import argon2 so the class can be instantiated even if
        # argon2-cffi is not installed (it raises at _upgrade time instead).
        self._argon2_hasher: Any = None

    def _get_hasher(self) -> Any:
        if self._argon2_hasher is None:
            argon2 = _require_argon2()
            self._argon2_hasher = argon2.PasswordHasher(
                time_cost=self._time_cost,
                memory_cost=self._memory_cost,
                parallelism=self._parallelism,
            )
        return self._argon2_hasher

    async def verify_and_upgrade(self, raw_key: str) -> ApiKey | None:
        """Verify *raw_key* and upgrade its hash algorithm if needed.

        Steps
        -----
        1. Extract the ``key_id`` prefix (first 8 characters).
        2. Load the record from the store.
        3. Verify the raw key against the stored hash (bcrypt or argon2).
        4. On success, if the hash is bcrypt, re-hash with argon2 and persist.
        5. Return the (possibly updated) :class:`ApiKey` record, or ``None``.

        Parameters
        ----------
        raw_key:
            The full raw API key submitted by the client.

        Returns
        -------
        ApiKey | None
            The valid key record, or ``None`` if verification fails.
        """
        from mp_commons.security.apikeys.generator import _PREFIX_LEN  # noqa: PLC0415

        if len(raw_key) < _PREFIX_LEN:
            return None

        key_id = raw_key[:_PREFIX_LEN]
        record = await self._store.find_by_id(key_id)
        if record is None or not record.is_valid():
            return None

        key_hash = record.key_hash
        raw_bytes = raw_key.encode()

        if _is_bcrypt(key_hash):
            if not bcrypt.checkpw(raw_bytes, key_hash):
                return None
            # Upgrade to argon2
            try:
                new_hash = self._get_hasher().hash(raw_key)
                upgraded = ApiKey(
                    key_id=record.key_id,
                    key_hash=new_hash.encode() if isinstance(new_hash, str) else new_hash,
                    principal_id=record.principal_id,
                    scopes=record.scopes,
                    expires_at=record.expires_at,
                    revoked=record.revoked,
                )
                await self._store.save(upgraded)
                logger.info(
                    "api_key.hash_upgraded key_id=%s algorithm=argon2id",
                    key_id,
                )
                return upgraded
            except Exception:
                logger.exception("api_key.hash_upgrade_failed key_id=%s", key_id)
                # Return the original valid record even if upgrade fails
                return record

        if _is_argon2(key_hash):
            try:
                hasher = self._get_hasher()
                hash_str = key_hash.decode() if isinstance(key_hash, bytes) else key_hash
                hasher.verify(hash_str, raw_key)
                # Check if rehash is needed (e.g. params changed)
                if hasher.check_needs_rehash(hash_str):
                    new_hash = hasher.hash(raw_key)
                    upgraded = ApiKey(
                        key_id=record.key_id,
                        key_hash=new_hash.encode() if isinstance(new_hash, str) else new_hash,
                        principal_id=record.principal_id,
                        scopes=record.scopes,
                        expires_at=record.expires_at,
                        revoked=record.revoked,
                    )
                    await self._store.save(upgraded)
                    logger.info(
                        "api_key.argon2_rehashed key_id=%s",
                        key_id,
                    )
                    return upgraded
                return record
            except Exception:
                return None

        # Unknown hash format — fall back to bcrypt check
        try:
            if bcrypt.checkpw(raw_bytes, key_hash):
                return record
        except Exception:
            pass
        return None


__all__ = ["ApiKeyHashUpgrade"]
