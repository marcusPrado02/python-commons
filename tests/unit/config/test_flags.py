"""Unit tests for §90 – Feature Flags."""

from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile

from mp_commons.config.flags import (
    EvaluationContext,
    FeatureFlagClient,
    FlatFileProvider,
)

_FLAGS_YAML = """\
simple_on:
  enabled: true

simple_off:
  enabled: false

half_rollout:
  rollout_percentage: 50

string_flag:
  value: "blue"

number_flag:
  value: 3.14

object_flag:
  value:
    theme: dark
    retries: 3

targeted_flag:
  targeting:
    - key: "vip-user"
      value: true
  enabled: false
"""


def _make_provider() -> tuple[FlatFileProvider, str]:
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        f.write(_FLAGS_YAML)
        path = f.name
    return FlatFileProvider(path), path


class TestFlatFileProvider:
    def test_simple_flag_enabled(self):
        provider, tmp = _make_provider()
        try:
            result = asyncio.run(provider.get_boolean("simple_on", False))
            assert result is True
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_simple_flag_disabled(self):
        provider, tmp = _make_provider()
        try:
            result = asyncio.run(provider.get_boolean("simple_off", True))
            assert result is False
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_missing_flag_returns_default(self):
        provider, tmp = _make_provider()
        try:
            result = asyncio.run(provider.get_boolean("nonexistent", True))
            assert result is True
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_targeting_rule_vip_user(self):
        provider, tmp = _make_provider()
        try:
            ctx = EvaluationContext(targeting_key="vip-user")
            result = asyncio.run(provider.get_boolean("targeted_flag", False, ctx))
            assert result is True
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_targeting_rule_non_vip(self):
        provider, tmp = _make_provider()
        try:
            ctx = EvaluationContext(targeting_key="regular-user")
            result = asyncio.run(provider.get_boolean("targeted_flag", False, ctx))
            assert result is False  # no targeting match, enabled=false
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_rollout_percentage_deterministic(self):
        provider, tmp = _make_provider()
        try:
            ctx = EvaluationContext(targeting_key="user-stable")
            r1 = asyncio.run(provider.get_boolean("half_rollout", False, ctx))
            r2 = asyncio.run(provider.get_boolean("half_rollout", False, ctx))
            assert r1 == r2  # deterministic
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_rollout_0_percent_always_off(self):
        import tempfile as tf

        content = "zero_flag:\n  rollout_percentage: 0\n"
        with tf.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write(content)
            tmp = f.name
        try:
            provider = FlatFileProvider(tmp)
            for user in [f"user-{i}" for i in range(20)]:
                ctx = EvaluationContext(targeting_key=user)
                r = asyncio.run(provider.get_boolean("zero_flag", True, ctx))
                assert r is False
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_rollout_100_percent_always_on(self):
        import tempfile as tf

        content = "full_flag:\n  rollout_percentage: 100\n"
        with tf.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write(content)
            tmp = f.name
        try:
            provider = FlatFileProvider(tmp)
            for user in [f"user-{i}" for i in range(20)]:
                ctx = EvaluationContext(targeting_key=user)
                r = asyncio.run(provider.get_boolean("full_flag", False, ctx))
                assert r is True
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_get_string(self):
        provider, tmp = _make_provider()
        try:
            result = asyncio.run(provider.get_string("string_flag", "red"))
            assert result == "blue"
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_get_string_default(self):
        provider, tmp = _make_provider()
        try:
            result = asyncio.run(provider.get_string("missing", "default"))
            assert result == "default"
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_get_number(self):
        provider, tmp = _make_provider()
        try:
            result = asyncio.run(provider.get_number("number_flag", 0.0))
            assert abs(result - 3.14) < 0.001
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_get_object(self):
        provider, tmp = _make_provider()
        try:
            result = asyncio.run(provider.get_object("object_flag", {}))
            assert result["theme"] == "dark"
            assert result["retries"] == 3
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_reload(self):
        provider, tmp = _make_provider()
        try:
            provider.reload()
            assert "simple_on" in provider._flags
        finally:
            Path(tmp).unlink(missing_ok=True)


class TestFeatureFlagClient:
    def test_is_enabled_delegates_to_provider(self):
        provider, tmp = _make_provider()
        try:
            client = FeatureFlagClient(provider)
            result = asyncio.run(client.is_enabled("simple_on"))
            assert result is True
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_is_enabled_returns_default_on_error(self):
        class _FailProvider:
            async def get_boolean(self, *args, **kwargs):
                raise RuntimeError("oops")

            async def get_string(self, *args, **kwargs):
                raise RuntimeError()

            async def get_number(self, *args, **kwargs):
                raise RuntimeError()

            async def get_object(self, *args, **kwargs):
                raise RuntimeError()

        client = FeatureFlagClient(_FailProvider())
        result = asyncio.run(client.is_enabled("flag", default=True))
        assert result is True

    def test_get_string_fallback(self):
        class _FailProvider:
            async def get_boolean(self, *args, **kwargs):
                raise RuntimeError()

            async def get_string(self, *args, **kwargs):
                raise RuntimeError()

            async def get_number(self, *args, **kwargs):
                raise RuntimeError()

            async def get_object(self, *args, **kwargs):
                raise RuntimeError()

        client = FeatureFlagClient(_FailProvider())
        assert asyncio.run(client.get_string("f", default="x")) == "x"
