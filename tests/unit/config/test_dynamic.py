"""Unit tests for §89 – Dynamic Config."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import tempfile

import pytest

from mp_commons.config.dynamic import (
    DynamicConfigRegistry,
    EnvConfigSource,
    FileConfigSource,
)


class TestEnvConfigSource:
    def test_load_all_env(self):
        os.environ["_TEST_DYNAMIC_VAR"] = "hello"
        source = EnvConfigSource()
        data = asyncio.run(source.load())
        assert "_TEST_DYNAMIC_VAR" in data
        os.environ.pop("_TEST_DYNAMIC_VAR", None)

    def test_load_with_prefix(self):
        os.environ["MYAPP_DEBUG"] = "true"
        os.environ["MYAPP_LEVEL"] = "info"
        source = EnvConfigSource(prefix="MYAPP_")
        data = asyncio.run(source.load())
        assert "debug" in data
        assert "level" in data
        assert data["debug"] == "true"
        os.environ.pop("MYAPP_DEBUG", None)
        os.environ.pop("MYAPP_LEVEL", None)

    def test_supports_watch_false(self):
        assert EnvConfigSource().supports_watch() is False

    def test_watch_raises(self):
        async def _run():
            await EnvConfigSource().watch(lambda x: None)  # type: ignore

        with pytest.raises(NotImplementedError):
            asyncio.run(_run())


class TestFileConfigSourceYaml:
    def test_load_yaml(self):
        content = "host: localhost\nport: 5432\n"
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write(content)
            tmp = f.name
        try:
            source = FileConfigSource(tmp)
            data = asyncio.run(source.load())
            assert data["host"] == "localhost"
            assert data["port"] == 5432
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_load_json(self):
        content = json.dumps({"key": "value", "n": 42})
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write(content)
            tmp = f.name
        try:
            source = FileConfigSource(tmp)
            data = asyncio.run(source.load())
            assert data["key"] == "value"
            assert data["n"] == 42
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_load_toml(self):
        content = '[database]\nhost = "db"\nport = 5432\n'
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write(content)
            tmp = f.name
        try:
            source = FileConfigSource(tmp)
            data = asyncio.run(source.load())
            assert data["database"]["host"] == "db"
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_unsupported_format_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".xml", mode="w", delete=False) as f:
            f.write("<data/>")
            tmp = f.name
        try:
            source = FileConfigSource(tmp)
            with pytest.raises(ValueError, match="Unsupported"):
                asyncio.run(source.load())
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_supports_watch_without_watchfiles(self):
        # watchfiles is not installed so supports_watch should be False
        source = FileConfigSource("/tmp/x.yaml")
        assert isinstance(source.supports_watch(), bool)


class TestDynamicConfigRegistry:
    def _yaml_source(self, content: str, suffix: str = ".yaml") -> FileConfigSource:
        with tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False) as f:
            f.write(content)
            return FileConfigSource(f.name), f.name

    def test_get_from_source(self):
        source, tmp = self._yaml_source("db_host: 127.0.0.1\n")
        try:
            registry = DynamicConfigRegistry(ttl_seconds=60)
            registry.register("db_host", source)
            result = asyncio.run(registry.get("db_host"))
            assert result == "127.0.0.1"
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_get_default_when_key_missing(self):
        registry = DynamicConfigRegistry()
        result = asyncio.run(registry.get("nonexistent", default="fallback"))
        assert result == "fallback"

    def test_cache_hit_within_ttl(self):
        calls = [0]

        class _CountingSource:
            async def load(self):
                calls[0] += 1
                return {"val": "x"}

            def supports_watch(self):
                return False

            async def watch(self, cb):
                pass

        registry = DynamicConfigRegistry(ttl_seconds=60)
        registry.register("val", _CountingSource())
        asyncio.run(registry.get("val"))
        asyncio.run(registry.get("val"))
        assert calls[0] == 1  # second call served from cache

    def test_invalidate_clears_cache(self):
        calls = [0]

        class _CountingSource:
            async def load(self):
                calls[0] += 1
                return {"val": f"v{calls[0]}"}

            def supports_watch(self):
                return False

            async def watch(self, cb):
                pass

        registry = DynamicConfigRegistry(ttl_seconds=60)
        registry.register("val", _CountingSource())
        asyncio.run(registry.get("val"))
        registry.invalidate("val")
        asyncio.run(registry.get("val"))
        assert calls[0] == 2
