"""Preconfigured base settings class with all configuration sources wired up.

Don't touch this module unless you have good reason to. To add settings, go to `config.py`.
"""

import logging
import os
import time
from typing import Any

from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from src.project_base.constants import PACKAGE_NAME
from src.project_base.paths import ROOT
from src.project_base.settings.enums import Environment

logger = logging.getLogger(__name__)

ENVIRONMENT_VARIABLE_PREFIX = f"{PACKAGE_NAME.replace('-', '_').upper()}_"
"""Prefix for all environment variables that map to settings fields."""

_ENVIRONMENT_VARIABLE_NESTED_DELIMITER = "__"


class PreconfiguredSettings(BaseSettings):
    """Base class that wires up all configuration sources.

    Don't touch this class unless you have good reason to. To add settings, go to `Settings`.
    """

    model_config = SettingsConfigDict(extra="ignore")
    environment: Environment
    """Runtime environment.

    If not passed explicitly, may have been determined by the
    `{ENVIRONMENT_VARIABLE_PREFIX}ENVIRONMENT` environment variable.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        start_time = time.perf_counter()
        logger.debug("Starting Pydantic settings loading and validation...")

        try:
            super().__init__(*args, **kwargs)
        finally:
            end_time = time.perf_counter()
            duration = end_time - start_time
            logger.debug(f"Settings loaded in {duration:.4f} seconds.")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Determine configuration sources and their priority.

        Stuff earlier in the list overrides stuff later in the list.
        """
        env_settings_source = EnvSettingsSource(
            settings_cls,
            env_prefix=ENVIRONMENT_VARIABLE_PREFIX,
            env_nested_delimiter=_ENVIRONMENT_VARIABLE_NESTED_DELIMITER,
        )

        dotenv_settings_source = DotEnvSettingsSource(
            settings_cls,
            env_file=ROOT / ".env",
            env_file_encoding="utf-8",
            env_prefix=ENVIRONMENT_VARIABLE_PREFIX,
            env_nested_delimiter=_ENVIRONMENT_VARIABLE_NESTED_DELIMITER,
        )

        # This shouldn't happen since Pylance will complain if `environment` is not passed, but this
        # method runs before instantiation so it's still runtime unsafe to depend on the argument.
        try:
            passed_environment: Environment = init_settings.init_kwargs["environment"]  # type: ignore[reportAttributeAccessIssue]
        except KeyError as e:
            message = "You forgot to provide the `environment` argument to Settings()."
            raise TypeError(message) from e

        names = [
            f"config.{passed_environment}.local.yaml",
            f"config.{passed_environment}.yaml",
            "config.local.yaml",
            "config.yaml",
        ]
        yaml_setting_sources = [
            YamlConfigSettingsSource(settings_cls, yaml_file=ROOT / name) for name in names
        ]

        return (init_settings, env_settings_source, dotenv_settings_source, *yaml_setting_sources)


def runtime_environment() -> Environment:
    """Determine the runtime environment based on the environment variable."""
    env_var_name = f"{ENVIRONMENT_VARIABLE_PREFIX}ENVIRONMENT"
    env_value = os.getenv(env_var_name, "dev").lower()
    try:
        return Environment(env_value)
    except ValueError as ve:
        message = (
            f"Invalid environment '{env_value}' in {env_var_name}. Must be one of "
            f"{[e.value for e in Environment]}."
        )
        raise ValueError(message) from ve
