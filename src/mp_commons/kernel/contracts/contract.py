"""Kernel contracts – Contract, registry, and loader ports."""
from __future__ import annotations

import abc
import dataclasses
from typing import Any

from mp_commons.kernel.contracts.compatibility import CompatibilityMode

type SchemaVersion = int
type ContractId = str


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
    "OpenAPILoader",
    "SchemaVersion",
]
