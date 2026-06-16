"""Pydantic models for settings groups.

Add new models here (or in separate files alongside this one) for domain-specific settings.
For example, create ``database.py``, ``api.py``, or ``cache.py`` as needed.
"""

from pydantic import BaseModel

from .enums import LogLevel


class Logging(BaseModel):
    """Logging configuration settings."""

    log_level: LogLevel
    """Minimum log level for console application-facing logs emitted by your code.

    All logs from loggers named `{PACKAGE_NAME}.*` are affected by this setting. Lower-severity
    records will still be persisted by more verbose handlers, such as a DEBUG-level file log.
    """

    third_party_log_level: LogLevel
    """Minimum log level for console application-facing logs emitted by other libraries.

    You probably want this at INFO or WARNING unless you're hunting for a bug, in which case you may
    set it to DEBUG.

    Lower-severity records will still be persisted by more verbose handlers, such as a DEBUG-level
    file log.
    """
