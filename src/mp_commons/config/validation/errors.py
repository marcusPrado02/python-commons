"""Config validation errors."""
from mp_commons.kernel.errors import ApplicationError


class ConfigError(ApplicationError):
    """Raised when configuration is invalid or loading failed."""
    default_code = "config_error"


class MissingRequiredSettingError(ConfigError):
    """A required environment variable / setting is absent."""
    default_code = "missing_required_setting"

    def __init__(self, setting_name: str) -> None:
        super().__init__(f"Required setting '{setting_name}' is missing")
        self.setting_name = setting_name


class InvalidSettingValueError(ConfigError):
    """A setting's value is present but semantically invalid."""
    default_code = "invalid_setting_value"

    def __init__(self, setting_name: str, value: object, reason: str) -> None:
        super().__init__(
            f"Setting '{setting_name}' has invalid value {value!r}: {reason}"
        )
        self.setting_name = setting_name
        self.value = value
        self.reason = reason


__all__ = ["ConfigError", "InvalidSettingValueError", "MissingRequiredSettingError"]
