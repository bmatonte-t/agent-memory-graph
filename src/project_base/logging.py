"""Utility functions to handle logging in the whole project."""

from __future__ import annotations

import logging
import sys
import warnings
from copy import copy
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

from asgi_correlation_id import CorrelationIdFilter

from .constants import PACKAGE_NAME
from .paths import LOGS, PACKAGE

if TYPE_CHECKING:
    from os import PathLike
    from types import TracebackType
    from typing import TextIO

    from .settings.models import CloudLogging, Logging


class CorrelationIdFormatter(logging.Formatter):
    """Formatter that prefixes the `correlation_id` to the logged message if it exists.

    This works in conjunction with the `asgi_correlation_id.CorrelationIdFilter`, which will add the
    `correlation_id` attribute to any `LogRecord` if the `asgi_correlation_id.correlation_id`
    `ContextVar` is set to some value other than `None`.

    If the `LogRecord` has the `correlation_id` attribute, the formatter will **prefix the message**
    with the string `f"[{correlation_id}] "` so that filtering on the ID yields all the logs
    associated with a given API request.

    If the attribute isn't present (i.e.: the `ContextVar` wasn't set at the time the filter got
    called), then the message won't get any ID added.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the message depending on whether `record.correlation_id` exists.

        See the class level docstring for an explanation on what the formatter does.

        Args:
            record: The LogRecord to format.

        Returns:
            str: The formatted log.
        """
        # record will always have correlation_id because of our filter.
        if getattr(record, "correlation_id", None):
            # If correlation_id attr exists, edit message in place to prepend it to the message.
            # Each handler has its own formatter, so the record would get mutated and the UUID
            # prefixed many times as the LogRecord goes through each handler's formatter.
            record = copy(record)
            record.msg = f"[{record.correlation_id}] {record.msg}"  # type: ignore[reportAttributeAccess]
        return super().format(record)


class InfiniteTimestampFileHandler(RotatingFileHandler):
    """Roll over the log file by appending a timestamp suffix when it exceeds a certain size.

    This handler writes logs to the file at `filename` until the file size exceeds `max_bytes`. When
    that happens, the log file is rolled over by renaming it with a timestamp suffix.

    The timestamp used for naming is ISO 8601-formatted with microsecond precision. Microseconds are
    used to avoid collisions when multiple rollovers happen within the same second.

    This handler does not delete old log files, so you may want to implement a separate log pruning
    strategy (e.g., a cron job that deletes log files older than a certain age) to manage disk
    space. Otherwise, you may use the `RotatingFileHandler` from the standard library, which keeps a
    fixed number of backup files and deletes the oldest when rolling over.

    Args:
        filename: The base filename for the log file. Rolled over log files will be created by
            renaming this file with a timestamp suffix (and will therefore be located in the same
            directory).

            The active log file will always have this name.
        max_bytes: The maximum size in bytes of the log file before it gets rolled over. If 0, no
            rollover based on file size is performed. Defaults to 10 MB.
    """

    def __init__(self, filename: str | PathLike[str], max_bytes: int = 10 * 1024 * 1024) -> None:
        # backupCount=0 as dummy value since we entirely override rollover logic.
        super().__init__(filename, maxBytes=max_bytes, backupCount=0, delay=True)

        self.base_filename = Path(self.baseFilename)

    def doRollover(self) -> None:  # noqa: N802 must comply with parent method signature
        """Roll over the log file by appending a timestamp suffix when it exceeds `maxBytes`."""
        if self.stream:
            self.stream.close()
            self.stream = None  # type: ignore[reportAttributeAccessIssue]; parent class does this, stream can be None.

        if self.maxBytes > 0:
            timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S.%fZ")
            backup_path = self.base_filename.with_stem(f"{self.base_filename.stem}_{timestamp}")

            if self.base_filename.exists():
                self.base_filename.rename(backup_path)

        if not self.delay:
            self.stream = self._open()


APP_LOGGER = logging.getLogger(PACKAGE_NAME)  # To configure logging for your library.
MODULE_LOGGER = logging.getLogger("__main__")  # To configure logging where you python run a file.
ROOT_LOGGER = logging.getLogger("root")  # To configure logging for 3rd party libraries.

_log_format = "%(asctime)s - %(levelname)s - %(name)s.%(funcName)s:%(lineno)d - %(message)s"

logger = logging.getLogger(__name__)


class LoggingConfiguration:
    """Configure logging."""

    def __init__(self) -> None:
        self._is_configured = False

    def configure_logging(
        self,
        configuration: Logging,
        cloud_logging: CloudLogging | None = None,
    ) -> None:
        """Configures the logging for the application. This function should only be run once.

        Just use the common pattern

            ```python
            logger = logging.getLogger(__name__)
            ```

        The root logger is used to configure logging for 3rd party libraries. Logs from our library
        should be emitted from children of the APP_LOGGER (named `PACKAGE_NAME`).

        All logs from all libraries are emitted to a log file at ``LOGS / "app.log"``. Logs are
        also emitted to the console via a `StreamHandler` if they are at least of the level
        specified.

        If you want Correlation IDs to be prepended to logs, ensure you set the `correlation_id`
        `ContextVar` from the `asgi_correlation_id` package (for example using the
        `CorrelationIdMiddleware` in FastAPI apps).

        In this setup, all logs are emitted to sinks (terminal or file) from either the
        `APP_LOGGER`, a `MODULE_LOGGER` or the `ROOT_LOGGER` (or their children). Logs emitted from
        other loggers are propagated until they reach one of these three loggers, which finally
        handle them.

        Args:
            configuration: The logging configuration to use. See documentation in the `Logging`
                model for more details on the available settings.
            cloud_logging: Optional Cloud Logging configuration. When provided and `enabled` is
                `True`, attaches a Cloud Logging handler that exports structured JSON logs to
                Google Cloud Logging. Defaults to None (no Cloud Logging).
        """
        if self._is_configured:
            warnings.warn(
                (
                    "Logging already configured. Please don't run configure_logging more than once."
                    " Skipping."
                ),
                stacklevel=2,
            )
            return

        formatter = CorrelationIdFormatter(_log_format)

        # Configure handlers
        root_console = logging.StreamHandler()
        root_console.setFormatter(formatter)
        root_console.setLevel(configuration.third_party_log_level)

        package_console = logging.StreamHandler()
        package_console.setFormatter(formatter)
        package_console.setLevel(configuration.log_level)

        LOGS.mkdir(exist_ok=True)
        file = InfiniteTimestampFileHandler(LOGS / "app.log")
        file.setFormatter(formatter)
        file.setLevel("DEBUG")  # DEBUG to ensure we log everything to file.

        # Logger level only affects what logs emitted by this logger get passed to its handlers. The
        # LogRecords are always propagated to parent loggers. We want all records to be passed to
        # handlers because the file handler needs DEBUG level.
        for _logger in (APP_LOGGER, MODULE_LOGGER):
            _logger.setLevel("DEBUG")
            _logger.addHandler(file)
            _logger.addHandler(package_console)
            _logger.propagate = False

        # Setting this is mandatory because all children loggers will inherit this level (because
        # their level is `NOTSET`). We want all children logger to forward all level logs because we
        # always want to log everything to the file.
        ROOT_LOGGER.setLevel("DEBUG")
        ROOT_LOGGER.addHandler(file)
        ROOT_LOGGER.addHandler(root_console)

        _add_correlation_id_to_logs = CorrelationIdFilter()
        # _add_correlation_id_to_logs added to handlers because logger level filters only affect
        # LogRecords emitted by the logger itself, not any children loggers.
        for _logger in (ROOT_LOGGER, APP_LOGGER, MODULE_LOGGER):
            for handler in _logger.handlers:
                if _add_correlation_id_to_logs not in handler.filters:
                    handler.addFilter(_add_correlation_id_to_logs)

        self._install_warnings_hook()
        self._install_exception_hook()

        if cloud_logging is not None and cloud_logging.enabled:
            self._install_cloud_logging_handler(
                project_id=cloud_logging.project_id,
                labels=dict(cloud_logging.labels),
                log_level=configuration.log_level,
            )

        logger.debug("========== NEW EXECUTION ==========")
        logger.debug("Logging configured.")

        self._is_configured = True

    @staticmethod
    def _install_cloud_logging_handler(
        project_id: str | None,
        labels: dict[str, str],
        log_level: str,
    ) -> None:
        """Attach a Cloud Logging handler to the root Python logger.

        The handler exports structured JSON log entries to Google Cloud Logging.
        Falls back gracefully with a warning when the client library is unavailable or
        authentication fails.

        Args:
            project_id: GCP project identifier. When None, falls back to ADC project.
            labels: Resource labels attached to every exported log entry.
            log_level: Minimum log level to export to Cloud Logging.
        """
        del labels
        try:
            import google.cloud.logging  # noqa: PLC0415

            client_kwargs: dict[str, object] = {}
            if project_id:
                client_kwargs["project"] = project_id

            client = google.cloud.logging.Client(**client_kwargs)
            handler = client.get_default_handler()
            handler.setLevel(log_level)
            root_logger = logging.getLogger()
            root_logger.addHandler(handler)
            logger.info(
                "cloud_logging_handler_installed project=%s",
                project_id or "(from ADC)",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "cloud_logging_handler_unavailable reason=%s",
                exc,
            )

    @staticmethod
    def _install_warnings_hook() -> None:
        """Route warnings through the correct logger based on origin.

        Own-code warnings (files inside the package directory) go through `APP_LOGGER`, so they
        are governed by `log_level`. Third-party warnings propagate through `py.warnings` to
        `ROOT_LOGGER`, governed by `third_party_log_level`.
        """
        original_showwarning = warnings.showwarning
        app_warning_logger = APP_LOGGER.getChild("warnings")
        third_party_warning_logger = logging.getLogger("py.warnings")  # Same as captureWarnings.

        def handle_warning(
            message: Warning | str,
            category: type[Warning],
            filename: str,
            lineno: int,
            file: TextIO | None = None,
            line: str | None = None,
        ) -> None:
            # Respect an explicit file destination so callers opting out of logging keep the
            # standard warnings behavior.
            if file is not None:
                original_showwarning(message, category, filename, lineno, file=file, line=line)
                return
            formatted_warning = warnings.formatwarning(message, category, filename, lineno, line)

            is_own_code = Path(filename).is_relative_to(PACKAGE)
            target_logger = app_warning_logger if is_own_code else third_party_warning_logger

            target_logger.warning(formatted_warning)

        warnings.showwarning = handle_warning

    @staticmethod
    def _install_exception_hook() -> None:
        """Log uncaught exceptions before delegating to the original excepthook."""
        original_excepthook = sys.excepthook

        def handle_exception(
            exc_type: type[BaseException], exc_value: BaseException, exc_traceback: TracebackType
        ) -> None:
            """Log uncaught exceptions. Arguments are the same as sys.excepthook."""
            logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            original_excepthook(exc_type, exc_value, exc_traceback)

        sys.excepthook = handle_exception


configure_logging = LoggingConfiguration().configure_logging
