"""Unit tests for kernel contracts."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.kernel.contracts import (
    CompatibilityMode,
    Contract,
    ContractId,
    ContractRegistry,
    ContractVersion,
)


# ---------------------------------------------------------------------------
# CompatibilityMode enum (6.1)
# ---------------------------------------------------------------------------


class TestCompatibilityMode:
    def test_values_exist(self) -> None:
        assert CompatibilityMode.BACKWARD
        assert CompatibilityMode.FORWARD
        assert CompatibilityMode.FULL
        assert CompatibilityMode.NONE

    def test_all_modes_distinct(self) -> None:
        modes = {
            CompatibilityMode.BACKWARD,
            CompatibilityMode.FORWARD,
            CompatibilityMode.FULL,
            CompatibilityMode.NONE,
        }
        assert len(modes) == 4


# ---------------------------------------------------------------------------
# ContractVersion (6.2)
# ---------------------------------------------------------------------------


class TestContractVersion:
    def test_str_representation(self) -> None:
        v = ContractVersion(major=1, minor=2, patch=3)
        assert str(v) == "1.2.3"

    def test_ordering(self) -> None:
        v1 = ContractVersion(1, 0, 0)
        v2 = ContractVersion(1, 1, 0)
        v3 = ContractVersion(2, 0, 0)
        assert v1 < v2 < v3

    def test_patch_ordering(self) -> None:
        v1 = ContractVersion(1, 0, 0)
        v2 = ContractVersion(1, 0, 1)
        assert v1 < v2

    def test_equality(self) -> None:
        assert ContractVersion(1, 2, 3) == ContractVersion(1, 2, 3)

    def test_frozen(self) -> None:
        v = ContractVersion(1, 0, 0)
        with pytest.raises((AttributeError, TypeError)):
            v.major = 2  # type: ignore[misc]

    def test_from_str_valid(self) -> None:
        v = ContractVersion.from_str("3.5.1")
        assert v.major == 3
        assert v.minor == 5
        assert v.patch == 1
        assert str(v) == "3.5.1"

    def test_from_str_roundtrip(self) -> None:
        v = ContractVersion(1, 2, 3)
        assert ContractVersion.from_str(str(v)) == v

    def test_from_str_invalid_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            ContractVersion.from_str("not-a-version")

    def test_from_str_missing_part_raises(self) -> None:
        with pytest.raises(ValueError):
            ContractVersion.from_str("1.2")

    def test_from_str_non_numeric_raises(self) -> None:
        with pytest.raises(ValueError):
            ContractVersion.from_str("a.b.c")

    def test_max_version(self) -> None:
        versions = [
            ContractVersion(1, 0, 0),
            ContractVersion(2, 0, 0),
            ContractVersion(1, 5, 0),
        ]
        assert max(versions) == ContractVersion(2, 0, 0)


# ---------------------------------------------------------------------------
# Contract dataclass (6.3)
# ---------------------------------------------------------------------------


class TestContractDataclass:
    def test_contract_has_id_and_version(self) -> None:
        # ContractId is type alias for str; version is SchemaVersion (int)
        c = Contract(
            id="order-placed",
            version=1,
            mode=CompatibilityMode.BACKWARD,
            schema={"type": "object"},
        )
        assert c.id == "order-placed"
        assert c.version == 1


# ---------------------------------------------------------------------------
# ContractRegistry list_versions (6.3)
# ---------------------------------------------------------------------------


class InMemoryContractRegistry(ContractRegistry):
    """Test stub: stores (Contract, ContractVersion) pairs."""

    def __init__(self) -> None:
        self._entries: list[tuple[Contract, ContractVersion]] = []

    def _add(self, contract: Contract, semantic: ContractVersion) -> None:
        self._entries.append((contract, semantic))

    async def register(self, contract: Contract) -> None:
        # minimal impl: derive semantic version from SchemaVersion int
        v = contract.version  # int
        self._entries.append((contract, ContractVersion(v, 0, 0)))

    async def get(self, id: ContractId, version: object) -> Contract | None:
        for c, _ in self._entries:
            if c.id == id and c.version == version:
                return c
        return None

    async def check_compatibility(self, existing: Contract, candidate: Contract) -> bool:
        return candidate.version >= existing.version

    async def list_versions(self, id: ContractId) -> list[ContractVersion]:
        return sorted(sv for c, sv in self._entries if c.id == id)


class TestContractRegistryListVersions:
    def test_list_versions_empty(self) -> None:
        reg = InMemoryContractRegistry()
        result = asyncio.run(reg.list_versions("unknown"))
        assert result == []

    def test_list_versions_sorted(self) -> None:
        reg = InMemoryContractRegistry()
        cid: ContractId = "payment-received"

        async def _run() -> list[ContractVersion]:
            for i, ver_str in enumerate(("1.2.0", "2.0.0", "1.0.0"), start=1):
                reg._add(
                    Contract(id=cid, version=i, mode=CompatibilityMode.BACKWARD, schema={}),
                    ContractVersion.from_str(ver_str),
                )
            return await reg.list_versions(cid)

        versions = asyncio.run(_run())
        assert versions == [
            ContractVersion(1, 0, 0),
            ContractVersion(1, 2, 0),
            ContractVersion(2, 0, 0),
        ]

    def test_list_versions_multiple_contracts(self) -> None:
        reg = InMemoryContractRegistry()

        async def _run() -> None:
            reg._add(Contract(id="a", version=1, mode=CompatibilityMode.FULL, schema={}), ContractVersion(1, 0, 0))
            reg._add(Contract(id="b", version=2, mode=CompatibilityMode.NONE, schema={}), ContractVersion(2, 0, 0))
            assert len(await reg.list_versions("a")) == 1
            assert len(await reg.list_versions("b")) == 1

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Public surface smoke test (6.4)
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.kernel.contracts")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing from mp_commons.kernel.contracts"
