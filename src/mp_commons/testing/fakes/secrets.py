"""Testing fakes – FakeSecretStore (§36.10)."""
from __future__ import annotations

from mp_commons.config.secrets.port import SecretRef, SecretStore


class FakeSecretStore(SecretStore):
    """In-memory :class:`SecretStore` backed by a plain ``dict``.

    Use :meth:`seed` to pre-populate secrets before running the code under test.
    Raises :class:`KeyError` for any unknown secret.

    Usage::

        store = FakeSecretStore()
        store.seed("db/password", "s3cr3t")

        value = await store.get(SecretRef(path="db", key="password"))
        assert value == "s3cr3t"
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    # ------------------------------------------------------------------
    # SecretStore protocol
    # ------------------------------------------------------------------

    async def get(self, ref: SecretRef) -> str:
        key = str(ref)
        if key not in self._store:
            raise KeyError(f"Secret not found: {key}")
        return self._store[key]

    async def get_all(self, path: str) -> dict[str, str]:
        prefix = path.rstrip("/") + "/"
        return {
            k[len(prefix):]: v
            for k, v in self._store.items()
            if k.startswith(prefix)
        }

    # ------------------------------------------------------------------
    # Test-setup helpers
    # ------------------------------------------------------------------

    def seed(self, key: str, value: str) -> "FakeSecretStore":
        """Pre-populate *key* → *value*.

        *key* should match the string representation of a :class:`SecretRef`,
        i.e. ``"<path>/<secret_key>"``.
        """
        self._store[key] = value
        return self

    def seed_ref(self, ref: SecretRef, value: str) -> "FakeSecretStore":
        """Convenience overload that accepts a :class:`SecretRef` directly."""
        self._store[str(ref)] = value
        return self

    def reset(self) -> None:
        """Clear all seeded secrets."""
        self._store.clear()


__all__ = ["FakeSecretStore"]
