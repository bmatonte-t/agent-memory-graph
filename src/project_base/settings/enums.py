"""Enums for settings configuration."""

from enum import StrEnum


class Environment(StrEnum):
    """Supported application environments.

    You may add your own environments as needed.
    """

    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"


class LogLevel(StrEnum):
    """Supported log levels.

    Must match the log levels supported by the Python logging module for compatibility.
    """

    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"
    NOTSET = "NOTSET"
