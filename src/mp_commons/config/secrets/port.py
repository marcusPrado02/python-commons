"""Config secrets – SecretRef and SecretStore port."""
from __future__ import annotations

import abc
import dataclasses


@dataclasses.dataclass(frozen=True)
class SecretRef:
    """Reference to a secret stored externally."""
    path: str
    key: str
    version: str | None = None

    def __str__(self) -> str:
        return f"{self.path}/{self.key}"


class SecretStore(abc.ABC):
    """Port: retrieve secrets from a backend."""

    @abc.abstractmethod
    async def get(self, ref: SecretRef) -> str: ...

    @abc.abstractmethod
    async def get_all(self, path: str) -> dict[str, str]: ...


__all__ = ["SecretRef", "SecretStore"]
