"""Unit tests for config secrets (§24)."""

from __future__ import annotations

import asyncio
import pathlib
import tempfile

import pytest

from mp_commons.config.secrets import (
    KubernetesSecretStore,
    SecretRef,
    SecretStore,
)


# ---------------------------------------------------------------------------
# §24.1  SecretRef dataclass
# ---------------------------------------------------------------------------


class TestSecretRef:
    def test_str_representation(self) -> None:
        ref = SecretRef(path="db", key="password")
        assert str(ref) == "db/password"

    def test_with_version(self) -> None:
        ref = SecretRef(path="db", key="password", version="v2")
        assert ref.version == "v2"

    def test_without_version_defaults_none(self) -> None:
        ref = SecretRef(path="app", key="secret")
        assert ref.version is None

    def test_is_frozen(self) -> None:
        ref = SecretRef(path="p", key="k")
        with pytest.raises((TypeError, Exception)):
            ref.path = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        r1 = SecretRef(path="x", key="y")
        r2 = SecretRef(path="x", key="y")
        assert r1 == r2


# ---------------------------------------------------------------------------
# §24.2  KubernetesSecretStore
# ---------------------------------------------------------------------------


class TestKubernetesSecretStore:
    def _make_store(self, tmp_path: pathlib.Path) -> tuple[KubernetesSecretStore, pathlib.Path]:
        store = KubernetesSecretStore(mount_root=str(tmp_path))
        return store, tmp_path

    def _write_secret(self, base: pathlib.Path, path: str, key: str, value: str) -> None:
        secret_dir = base / path
        secret_dir.mkdir(parents=True, exist_ok=True)
        (secret_dir / key).write_text(value)

    def test_get_reads_secret(self, tmp_path: pathlib.Path) -> None:
        store, base = self._make_store(tmp_path)
        self._write_secret(base, "myapp", "db-password", "s3cr3t")
        result = asyncio.run(store.get(SecretRef(path="myapp", key="db-password")))
        assert result == "s3cr3t"

    def test_get_strips_trailing_whitespace(self, tmp_path: pathlib.Path) -> None:
        store, base = self._make_store(tmp_path)
        self._write_secret(base, "app", "key", "  value  \n")
        result = asyncio.run(store.get(SecretRef(path="app", key="key")))
        assert result == "value"

    def test_get_missing_key_raises(self, tmp_path: pathlib.Path) -> None:
        store, base = self._make_store(tmp_path)
        (tmp_path / "app").mkdir()
        with pytest.raises(FileNotFoundError):
            asyncio.run(store.get(SecretRef(path="app", key="missing-key")))

    def test_get_all_reads_all_files(self, tmp_path: pathlib.Path) -> None:
        store, base = self._make_store(tmp_path)
        self._write_secret(base, "bundle", "alpha", "AAA")
        self._write_secret(base, "bundle", "beta", "BBB")
        result = asyncio.run(store.get_all("bundle"))
        assert result == {"alpha": "AAA", "beta": "BBB"}

    def test_get_all_empty_dir(self, tmp_path: pathlib.Path) -> None:
        store, base = self._make_store(tmp_path)
        (tmp_path / "empty-bundle").mkdir()
        result = asyncio.run(store.get_all("empty-bundle"))
        assert result == {}

    def test_get_all_strips_values(self, tmp_path: pathlib.Path) -> None:
        store, base = self._make_store(tmp_path)
        self._write_secret(base, "group", "k", "  value\n")
        result = asyncio.run(store.get_all("group"))
        assert result["k"] == "value"

    def test_default_mount_root(self) -> None:
        store = KubernetesSecretStore()
        assert store._root == "/var/run/secrets"

    def test_is_secret_store(self) -> None:
        assert isinstance(KubernetesSecretStore(), SecretStore)

    def test_get_multiple_secrets(self, tmp_path: pathlib.Path) -> None:
        store, base = self._make_store(tmp_path)
        self._write_secret(base, "svc", "token", "tok123")
        self._write_secret(base, "svc", "cert", "cert-data")

        token = asyncio.run(store.get(SecretRef(path="svc", key="token")))
        cert = asyncio.run(store.get(SecretRef(path="svc", key="cert")))

        assert token == "tok123"
        assert cert == "cert-data"
