"""Config secrets – KubernetesSecretStore."""
from __future__ import annotations

from mp_commons.config.secrets.port import SecretRef, SecretStore


class KubernetesSecretStore(SecretStore):
    """Reads secrets from Kubernetes environment variables / mounted files."""

    def __init__(self, mount_root: str = "/var/run/secrets") -> None:
        self._root = mount_root

    async def get(self, ref: SecretRef) -> str:
        import pathlib
        secret_path = pathlib.Path(self._root) / ref.path / ref.key
        if not secret_path.exists():
            raise FileNotFoundError(f"Secret not found: {secret_path}")
        return secret_path.read_text().strip()

    async def get_all(self, path: str) -> dict[str, str]:
        import pathlib
        base = pathlib.Path(self._root) / path
        return {f.name: f.read_text().strip() for f in base.iterdir() if f.is_file()}


__all__ = ["KubernetesSecretStore"]
