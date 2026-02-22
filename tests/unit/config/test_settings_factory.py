"""Unit tests – SettingsFactory and InvalidSettingValueError (§23.5, §25.3)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import ClassVar

import pytest

from mp_commons.config.settings import (
    EnvSettingsLoader,
    Settings,
    SettingsFactory,
)
from mp_commons.config.validation import (
    ConfigError,
    InvalidSettingValueError,
    MissingRequiredSettingError,
)


# ---------------------------------------------------------------------------
# Shared settings fixture
# ---------------------------------------------------------------------------


@dataclass
class ServiceSettings(Settings):
    _prefix: ClassVar[str] = "SVC"
    host: str = "localhost"
    port: int = 8080
    debug: bool = False


@dataclass
class RequiredSettings(Settings):
    _prefix: ClassVar[str] = "REQ"
    api_key: str  # no default → required


# ---------------------------------------------------------------------------
# §25.3 – InvalidSettingValueError
# ---------------------------------------------------------------------------


class TestInvalidSettingValueError:
    """§25.3 – InvalidSettingValueError carries name, value, and reason."""

    def test_attributes_are_set(self) -> None:
        err = InvalidSettingValueError("PORT", "abc", "must be an integer")
        assert err.setting_name == "PORT"
        assert err.value == "abc"
        assert err.reason == "must be an integer"

    def test_message_contains_all_parts(self) -> None:
        err = InvalidSettingValueError("PORT", "abc", "must be an integer")
        msg = err.to_dict()["message"]
        assert "PORT" in msg
        assert "abc" in msg
        assert "must be an integer" in msg

    def test_is_config_error(self) -> None:
        err = InvalidSettingValueError("X", 0, "out of range")
        assert isinstance(err, ConfigError)

    def test_default_code(self) -> None:
        err = InvalidSettingValueError("X", None, "reason")
        assert err.to_dict()["code"] == "invalid_setting_value"

    def test_none_value_repr_in_message(self) -> None:
        err = InvalidSettingValueError("KEY", None, "cannot be None")
        msg = err.to_dict()["message"]
        assert "None" in msg

    def test_can_be_raised_and_caught_as_config_error(self) -> None:
        with pytest.raises(ConfigError):
            raise InvalidSettingValueError("DB_URL", "", "empty string not allowed")


# ---------------------------------------------------------------------------
# §23.5 – SettingsFactory.create()
# ---------------------------------------------------------------------------


class TestSettingsFactory:
    """§23.5 – SettingsFactory merges loaders and applies overrides."""

    def test_overrides_only(self) -> None:
        """Factory with no loaders + overrides constructs a valid instance."""
        s = SettingsFactory.create(
            ServiceSettings,
            overrides={"host": "override-host", "port": 9000},
        )
        assert s.host == "override-host"
        assert s.port == 9000

    def test_defaults_used_when_no_override(self) -> None:
        s = SettingsFactory.create(ServiceSettings, overrides={"port": 1234})
        assert s.host == "localhost"  # default
        assert s.port == 1234

    def test_loader_values_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SVC_HOST", "from-env")
        s = SettingsFactory.create(ServiceSettings, loaders=[EnvSettingsLoader()])
        assert s.host == "from-env"

    def test_overrides_win_over_loaders(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SVC_HOST", "from-env")
        s = SettingsFactory.create(
            ServiceSettings,
            loaders=[EnvSettingsLoader()],
            overrides={"host": "from-override"},
        )
        assert s.host == "from-override"

    def test_missing_required_raises(self) -> None:
        with pytest.raises(MissingRequiredSettingError):
            SettingsFactory.create(RequiredSettings)

    def test_missing_required_overridden_by_override(self) -> None:
        s = SettingsFactory.create(
            RequiredSettings, overrides={"api_key": "secret"}
        )
        assert s.api_key == "secret"

    def test_empty_loaders_list_uses_defaults(self) -> None:
        s = SettingsFactory.create(ServiceSettings, loaders=[])
        assert s.host == "localhost"
        assert s.port == 8080

    def test_no_args_creates_default_settins(self) -> None:
        s = SettingsFactory.create(ServiceSettings)
        assert isinstance(s, ServiceSettings)

    def test_failing_loader_skipped_silently(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A loader that raises is skipped; overrides still apply."""
        monkeypatch.delenv("SVC_HOST", raising=False)

        class BrokenLoader(EnvSettingsLoader):
            def load(self, settings_class):  # type: ignore[override]
                raise RuntimeError("always broken")

        s = SettingsFactory.create(
            ServiceSettings,
            loaders=[BrokenLoader()],
            overrides={"host": "fallback"},
        )
        assert s.host == "fallback"
