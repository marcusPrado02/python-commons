"""Azure Key Vault secret store — implements SecretStore (A-08).

Uses ``azure-keyvault-secrets`` with managed-identity authentication via
``azure-identity``.  Async throughout using ``SecretClient`` from
``azure.keyvault.secrets.aio``.

Usage::

    from mp_commons.adapters.azure_keyvault import AzureKeyVaultSecretStore
    from mp_commons.config.secrets.port import SecretRef

    store = AzureKeyVaultSecretStore(
        vault_url="https://my-vault.vault.azure.net/",
    )

    # SecretRef.path → Azure secret name (slash-separated paths are
    # flattened to hyphens because Key Vault names cannot contain slashes).
    ref = SecretRef(path="database", key="password")
    password = await store.get(ref)
    all_secrets = await store.get_all("database")
"""
from __future__ import annotations

import logging
from typing import Any

from mp_commons.config.secrets.port import SecretRef, SecretStore

logger = logging.getLogger(__name__)


def _require_keyvault() -> Any:
    try:
        from azure.keyvault.secrets.aio import SecretClient  # type: ignore[import-untyped]
        return SecretClient
    except ImportError as exc:
        raise ImportError(
            "azure-keyvault-secrets is required for AzureKeyVaultSecretStore. "
            "Install it with: pip install 'azure-keyvault-secrets>=4.7'"
        ) from exc


def _require_identity() -> Any:
    try:
        from azure.identity.aio import DefaultAzureCredential  # type: ignore[import-untyped]
        return DefaultAzureCredential
    except ImportError as exc:
        raise ImportError(
            "azure-identity is required for managed-identity auth. "
            "Install it with: pip install 'azure-identity>=1.15'"
        ) from exc


def _secret_name(path: str, key: str) -> str:
    """Build an Azure Key Vault secret name from *path* and *key*.

    Azure Key Vault names must match ``^[a-zA-Z0-9-]+$``.  Slashes and
    underscores are replaced with hyphens.
    """
    raw = f"{path}-{key}" if path else key
    return raw.replace("/", "-").replace("_", "-")


class AzureKeyVaultSecretStore(SecretStore):
    """Async :class:`~mp_commons.config.secrets.port.SecretStore` backed by
    Azure Key Vault.

    Parameters
    ----------
    vault_url:
        Full Key Vault URI, e.g.
        ``https://my-vault.vault.azure.net/``.
    credential:
        Optional explicit credential (e.g. ``ClientSecretCredential``).
        Defaults to ``DefaultAzureCredential`` for managed-identity auth.
    """

    def __init__(
        self,
        vault_url: str,
        credential: Any = None,
    ) -> None:
        self._vault_url = vault_url
        self._credential = credential

    def _make_client(self) -> Any:
        SecretClient = _require_keyvault()
        credential = self._credential or _require_identity()()
        return SecretClient(vault_url=self._vault_url, credential=credential)

    async def get(self, ref: SecretRef) -> str:
        """Retrieve the secret identified by *ref*.

        Azure Key Vault does not support hierarchical secret names.  The
        ``path`` and ``key`` are combined into a single name using hyphens.
        An optional ``version`` is passed through.

        Raises
        ------
        KeyError
            If the secret does not exist.
        """
        name = _secret_name(ref.path, ref.key)
        async with self._make_client() as client:
            try:
                secret = await client.get_secret(name, version=ref.version)
                return secret.value
            except Exception as exc:
                exc_str = str(exc)
                if "SecretNotFound" in type(exc).__name__ or "404" in exc_str or "SecretNotFound" in exc_str:
                    raise KeyError(f"Secret '{name}' not found in vault") from exc
                raise

    async def get_all(self, path: str) -> dict[str, str]:
        """Return all secrets whose names start with *path*.

        The returned dict maps the raw Azure Key Vault secret name to its value.
        """
        async with self._make_client() as client:
            result: dict[str, str] = {}
            prefix = path.replace("/", "-").replace("_", "-")
            async for props in client.list_properties_of_secrets():
                if props.name and props.name.startswith(prefix) and props.enabled:
                    secret = await client.get_secret(props.name)
                    result[props.name] = secret.value
            return result


__all__ = ["AzureKeyVaultSecretStore"]
