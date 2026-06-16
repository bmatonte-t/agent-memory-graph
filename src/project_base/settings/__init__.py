"""Application configuration and settings management.

Usage:

    from project_base.settings import settings

    settings.logging.log_level

Importing the `settings` object triggers data loading and validation. You shouldn't notice this in
terms of speed since Pydantic is very fast, and errors in configuration schema will fail your
application on startup.

If you want to re-instantiate settings, you may do so directly:
    from project_base.settings.config import Settings
    from project_base.settings._core import runtime_environment

    settings = Settings(environment=runtime_environment())
"""

from ._core import ENVIRONMENT_VARIABLE_PREFIX, runtime_environment
from .config import Settings
from .enums import Environment

__all__ = ["ENVIRONMENT_VARIABLE_PREFIX", "Environment", "settings"]

settings = Settings(environment=runtime_environment())  # type: ignore[call-arg]
