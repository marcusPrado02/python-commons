"""Kernel contracts – Contract, registry, and loader ports."""
from __future__ import annotations

import abc
import dataclasses
from typing import Any

from mp_commons.kernel.contracts.compatibility import CompatibilityMode

type SchemaVersion = int
type ContractId = str


@dataclasses.dataclass(frozen=True, order=True)
class ContractVersion:
    """Semantic version for a contract schema.

    Supports full ordering so that ``v1 < v2`` comparisons work naturally.

    Example::

        v = ContractVersion.from_str("2.1.0")
        assert v.major == 2 and v.minor == 1 and v.patch == 0
    """

    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def from_str(cls, value: str) -> "ContractVersion":
        """Parse a ``"major.minor.patch"`` string."""
        parts = value.strip().split(".")
        if len(parts) != 3:  # noqa: PLR2004
            raise ValueError(f"Invalid ContractVersion string: {value!r}")
        major, minor, patch = (int(p) for p in parts)
        return cls(major=major, minor=minor, patch=patch)


@dataclasses.dataclass(frozen=True)
class Contract:
    """Represents a versioned API schema contract."""
    id: ContractId
    version: SchemaVersion
    mode: CompatibilityMode
    schema: dict[str, Any]


class ContractRegistry(abc.ABC):
    """Port: register, resolve, and validate schema contracts."""

    @abc.abstractmethod
    async def register(self, contract: Contract) -> None: ...

    @abc.abstractmethod
    async def get(self, id: ContractId, version: SchemaVersion) -> Contract | None: ...

    @abc.abstractmethod
    async def check_compatibility(self, existing: Contract, candidate: Contract) -> bool: ...

    @abc.abstractmethod
    async def list_versions(self, id: ContractId) -> list[ContractVersion]: ...


class OpenAPILoader(abc.ABC):
    """Port: load an OpenAPI specification from a source."""

    @abc.abstractmethod
    async def load(self, source: str) -> dict[str, Any]: ...


class AsyncAPILoader(abc.ABC):
    """Port: load an AsyncAPI specification from a source."""

    @abc.abstractmethod
    async def load(self, source: str) -> dict[str, Any]: ...


__all__ = [
    "AsyncAPILoader",
    "Contract",
    "ContractId",
    "ContractRegistry",
    "ContractVersion",
    "OpenAPILoader",
    "SchemaVersion",
]
