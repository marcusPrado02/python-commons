"""Kernel contracts – API schema contracts and compatibility modes."""
from mp_commons.kernel.contracts.compatibility import CompatibilityMode
from mp_commons.kernel.contracts.contract import (
    AsyncAPILoader,
    Contract,
    ContractId,
    ContractRegistry,
    OpenAPILoader,
    SchemaVersion,
)

__all__ = [
    "AsyncAPILoader",
    "CompatibilityMode",
    "Contract",
    "ContractId",
    "ContractRegistry",
    "OpenAPILoader",
    "SchemaVersion",
]
