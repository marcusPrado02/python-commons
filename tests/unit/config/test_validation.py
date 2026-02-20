"""Unit tests for config validation errors (§25)."""

from __future__ import annotations

import pytest

from mp_commons.config.validation import ConfigError, MissingRequiredSettingError
from mp_commons.kernel.errors import ApplicationError


# ---------------------------------------------------------------------------
# §25.1  ConfigError
# ---------------------------------------------------------------------------


class TestConfigError:
    def test_is_application_error(self) -> None:
        err = ConfigError("something went wrong")
        assert isinstance(err, ApplicationError)

    def test_default_code(self) -> None:
        err = ConfigError("bad")
        assert err.code == "config_error"

    def test_message_stored(self) -> None:
        err = ConfigError("invalid configuration")
        assert "invalid configuration" in str(err)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(ConfigError):
            raise ConfigError("test")

    def test_caught_as_application_error(self) -> None:
        with pytest.raises(ApplicationError):
            raise ConfigError("test")

    def test_custom_code_override(self) -> None:
        err = ConfigError("msg", code="custom_cfg")
        assert err.code == "custom_cfg"


# ---------------------------------------------------------------------------
# §25.2  MissingRequiredSettingError
# ---------------------------------------------------------------------------


class TestMissingRequiredSettingError:
    def test_is_config_error(self) -> None:
        err = MissingRequiredSettingError("FOO")
        assert isinstance(err, ConfigError)

    def test_is_application_error(self) -> None:
        err = MissingRequiredSettingError("FOO")
        assert isinstance(err, ApplicationError)

    def test_setting_name_stored(self) -> None:
        err = MissingRequiredSettingError("DATABASE_URL")
        assert err.setting_name == "DATABASE_URL"

    def test_message_contains_setting_name(self) -> None:
        err = MissingRequiredSettingError("SECRET_KEY")
        assert "SECRET_KEY" in str(err)

    def test_default_code(self) -> None:
        err = MissingRequiredSettingError("X")
        assert err.code == "missing_required_setting"

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(MissingRequiredSettingError) as exc_info:
            raise MissingRequiredSettingError("API_KEY")
        assert exc_info.value.setting_name == "API_KEY"

    def test_caught_as_config_error(self) -> None:
        with pytest.raises(ConfigError):
            raise MissingRequiredSettingError("X")

    def test_different_setting_names(self) -> None:
        names = ["DATABASE_URL", "REDIS_HOST", "API_SECRET", "JWT_KEY"]
        for name in names:
            err = MissingRequiredSettingError(name)
            assert err.setting_name == name
            assert name in str(err)
