"""Unit tests for config settings & validation (§23)."""

import os
from dataclasses import dataclass, field
from typing import ClassVar

import pytest

from mp_commons.config.settings import (
    EnvSettingsLoader,
    Settings,
    SettingsValidator,
)
from mp_commons.config.validation import ConfigError, MissingRequiredSettingError


# ---------------------------------------------------------------------------
# Concrete settings class used across tests
# ---------------------------------------------------------------------------


@dataclass
class AppSettings(Settings):
    _prefix: ClassVar[str] = "APP"

    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    allowed_origins: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# §23 — EnvSettingsLoader
# ---------------------------------------------------------------------------


class TestEnvSettingsLoader:
    def test_loads_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_HOST", "example.com")
        settings = EnvSettingsLoader().load(AppSettings)
        assert settings.host == "example.com"

    def test_loads_int(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_PORT", "9000")
        settings = EnvSettingsLoader().load(AppSettings)
        assert settings.port == 9000

    def test_loads_bool_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for truthy in ("true", "True", "1", "yes", "on"):
            monkeypatch.setenv("APP_DEBUG", truthy)
            settings = EnvSettingsLoader().load(AppSettings)
            assert settings.debug is True

    def test_loads_bool_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for falsy in ("false", "False", "0", "no", "off"):
            monkeypatch.setenv("APP_DEBUG", falsy)
            settings = EnvSettingsLoader().load(AppSettings)
            assert settings.debug is False

    def test_loads_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ALLOWED_ORIGINS", "http://a.com,http://b.com")
        settings = EnvSettingsLoader().load(AppSettings)
        assert settings.allowed_origins == ["http://a.com", "http://b.com"]

    def test_defaults_preserved_when_env_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in ("APP_HOST", "APP_PORT", "APP_DEBUG", "APP_ALLOWED_ORIGINS"):
            monkeypatch.delenv(key, raising=False)
        settings = EnvSettingsLoader().load(AppSettings)
        assert settings.host == "localhost"
        assert settings.port == 8080
        assert settings.debug is False
        assert settings.allowed_origins == []

    def test_env_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_HOST", "prod.example.com")
        monkeypatch.setenv("APP_PORT", "443")
        settings = EnvSettingsLoader().load(AppSettings)
        assert settings.host == "prod.example.com"
        assert settings.port == 443

    def test_missing_required_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import dataclasses

        @dataclass
        class StrictSettings(Settings):
            _prefix: ClassVar[str] = "STRICT"
            required_field: str = dataclasses.field()

            def __post_init__(self) -> None:
                pass  # skip _validate

        # required_field has no default — MissingRequiredSettingError expected
        monkeypatch.delenv("STRICT_REQUIRED_FIELD", raising=False)
        with pytest.raises(MissingRequiredSettingError) as exc_info:
            EnvSettingsLoader().load(StrictSettings)
        assert "STRICT_REQUIRED_FIELD" in str(exc_info.value)

    def test_returns_correct_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("APP_HOST", raising=False)
        settings = EnvSettingsLoader().load(AppSettings)
        assert isinstance(settings, AppSettings)


# ---------------------------------------------------------------------------
# §23 — SettingsValidator
# ---------------------------------------------------------------------------


class TestSettingsValidator:
    def test_no_errors_for_valid_settings(self) -> None:
        settings = AppSettings(host="ok.com", port=80, debug=False)
        errors = SettingsValidator().validate(settings)
        assert errors == []

    def test_reports_none_required_field(self) -> None:
        import dataclasses

        @dataclasses.dataclass
        class StandaloneSettings:
            name: str = dataclasses.field()

        obj = StandaloneSettings.__new__(StandaloneSettings)
        object.__setattr__(obj, "name", None)
        errors = SettingsValidator().validate(obj)
        assert any("name" in e for e in errors)


# ---------------------------------------------------------------------------
# §23 — ConfigErrors
# ---------------------------------------------------------------------------


class TestConfigErrors:
    def test_missing_required_setting_stores_name(self) -> None:
        err = MissingRequiredSettingError("DATABASE_URL")
        assert err.setting_name == "DATABASE_URL"
        assert "DATABASE_URL" in str(err)

    def test_is_config_error(self) -> None:
        err = MissingRequiredSettingError("X")
        assert isinstance(err, ConfigError)

    def test_config_error_code(self) -> None:
        err = ConfigError("bad config")
        assert err.code == "config_error"

    def test_missing_setting_error_code(self) -> None:
        err = MissingRequiredSettingError("FOO")
        assert err.code == "missing_required_setting"
