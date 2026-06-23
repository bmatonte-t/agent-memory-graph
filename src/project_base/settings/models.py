"""Pydantic models for settings groups.

Add new models here (or in separate files alongside this one) for domain-specific settings.
For example, create ``database.py``, ``api.py``, or ``cache.py`` as needed.
"""

from pydantic import BaseModel

from .enums import LogLevel


class CloudTrace(BaseModel):
    """Cloud Trace configuration for distributed tracing."""

    enabled: bool = False
    """`True` enables span export to Google Cloud Trace."""

    project_id: str | None = None
    """GCP project identifier for Cloud Trace export.

    When None and enabled is True, uses the project derived from Application Default Credentials.
    """


class CloudLogging(BaseModel):
    """Cloud Logging configuration for structured log export."""

    enabled: bool = False
    """`True` enables structured log export to Google Cloud Logging."""

    project_id: str | None = None
    """GCP project identifier for Cloud Logging export.

    When None and enabled is True, uses the project derived from Application Default Credentials.
    """

    labels: dict[str, str] = {}
    """Optional resource labels attached to every log entry."""


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
