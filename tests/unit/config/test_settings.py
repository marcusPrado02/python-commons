"""Unit tests for config settings & validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import pytest

from mp_commons.config.settings import EnvSettingsLoader, Settings
from mp_commons.config.validation import ConfigError, MissingRequiredSettingError


# ---------------------------------------------------------------------------
# Concrete settings class
# ---------------------------------------------------------------------------


@dataclass
class AppSettings(Settings):
    _prefix: str = field(default="APP", init=False, repr=False, compare=False)

    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    allowed_origins: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEnvSettingsLoader:
    def test_loads_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_HOST", "example.com")
        settings = EnvSettingsLoader.load(AppSettings)
        assert settings.host == "example.com"

    def test_loads_int(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_PORT", "9000")
        settings = EnvSettingsLoader.load(AppSettings)
        assert settings.port == 9000

    def test_loads_bool_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for truthy in ("true", "True", "1", "yes", "on"):
            monkeypatch.setenv("APP_DEBUG", truthy)
            settings = EnvSettingsLoader.load(AppSettings)
            assert settings.debug is True

    def test_loads_bool_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for falsy in ("false", "False", "0", "no", "off"):
            monkeypatch.setenv("APP_DEBUG", falsy)
            settings = EnvSettingsLoader.load(AppSettings)
            assert settings.debug is False

    def test_loads_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ALLOWED_ORIGINS", "http://a.com,http://b.com")
        settings = EnvSettingsLoader.load(AppSettings)
        assert settings.allowed_origins == ["http://a.com", "http://b.com"]

    def test_defaults_preserved_when_env_absent(self) -> None:
        # Ensure vars not set
        for key in ("APP_HOST", "APP_PORT", "APP_DEBUG", "APP_ALLOWED_ORIGINS"):
            os.environ.pop(key, None)
        settings = EnvSettingsLoader.load(AppSettings)
        assert settings.host == "localhost"
        assert settings.port == 8080
        assert settings.debug is False


class TestConfigErrors:
    def test_missing_required_setting_stores_name(self) -> None:
        err = MissingRequiredSettingError("DATABASE_URL")
        assert err.setting_name == "DATABASE_URL"
        assert "DATABASE_URL" in str(err)

    def test_is_config_error(self) -> None:
        err = MissingRequiredSettingError("X")
        assert isinstance(err, ConfigError)
