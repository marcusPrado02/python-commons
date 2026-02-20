"""Unit tests for feature flags — §13."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.application.feature_flags import (
    FeatureFlag,
    FeatureFlagProvider,
    InMemoryFeatureFlagProvider,
)


# ---------------------------------------------------------------------------
# FeatureFlag value object (13.1)
# ---------------------------------------------------------------------------


class TestFeatureFlag:
    def test_frozen(self) -> None:
        flag = FeatureFlag(key="dark_mode")
        with pytest.raises((AttributeError, TypeError)):
            flag.key = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        flag = FeatureFlag(key="my_flag")
        assert flag.default_value is False
        assert flag.description == ""
        assert flag.tags == frozenset()

    def test_with_metadata(self) -> None:
        flag = FeatureFlag(
            key="new_ui",
            description="New UI rollout",
            default_value=True,
            tags=frozenset({"beta", "ui"}),
        )
        assert flag.default_value is True
        assert "beta" in flag.tags


# ---------------------------------------------------------------------------
# InMemoryFeatureFlagProvider (13.3)
# ---------------------------------------------------------------------------


class TestInMemoryFeatureFlagProvider:
    def _flag(self, key: str = "my_flag", default: bool = False) -> FeatureFlag:
        return FeatureFlag(key=key, default_value=default)

    def test_disabled_by_default(self) -> None:
        provider = InMemoryFeatureFlagProvider()
        result = asyncio.run(provider.is_enabled(self._flag()))
        assert result is False

    def test_uses_flag_default_value(self) -> None:
        provider = InMemoryFeatureFlagProvider()
        result = asyncio.run(provider.is_enabled(self._flag(default=True)))
        assert result is True

    def test_set_enables_flag(self) -> None:
        provider = InMemoryFeatureFlagProvider()
        flag = self._flag()
        provider.set(flag, True)
        assert asyncio.run(provider.is_enabled(flag)) is True

    def test_set_disables_flag(self) -> None:
        provider = InMemoryFeatureFlagProvider()
        flag = self._flag()
        provider.set(flag, True)
        provider.set(flag, False)
        assert asyncio.run(provider.is_enabled(flag)) is False

    def test_set_by_string_key(self) -> None:
        provider = InMemoryFeatureFlagProvider()
        flag = self._flag(key="feature_x")
        provider.set("feature_x", True)
        assert asyncio.run(provider.is_enabled(flag)) is True

    def test_init_with_flags_dict(self) -> None:
        provider = InMemoryFeatureFlagProvider({"dark_mode": True, "beta": False})
        assert asyncio.run(provider.is_enabled(FeatureFlag(key="dark_mode"))) is True
        assert asyncio.run(provider.is_enabled(FeatureFlag(key="beta"))) is False

    def test_get_variant_on_true(self) -> None:
        provider = InMemoryFeatureFlagProvider()
        flag = self._flag()
        provider.set(flag, True)
        variant = asyncio.run(provider.get_variant(flag))
        assert variant == "on"

    def test_get_variant_on_false(self) -> None:
        provider = InMemoryFeatureFlagProvider()
        flag = self._flag()
        variant = asyncio.run(provider.get_variant(flag))
        assert variant == "off"

    def test_multiple_flags_independent(self) -> None:
        provider = InMemoryFeatureFlagProvider()
        f1 = self._flag(key="f1")
        f2 = self._flag(key="f2")
        provider.set(f1, True)
        assert asyncio.run(provider.is_enabled(f1)) is True
        assert asyncio.run(provider.is_enabled(f2)) is False


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.application.feature_flags")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing"
