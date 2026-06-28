"""Tests for the logging module."""

from __future__ import annotations

import io
import logging
import sys
import warnings
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from asgi_correlation_id import CorrelationIdFilter
from asgi_correlation_id.context import correlation_id

from src.project_base import logging as logging_module
from src.project_base.logging import (
    APP_LOGGER,
    MODULE_LOGGER,
    CorrelationIdFormatter,
    LoggingConfiguration,
    configure_logging,
)
from src.project_base.paths import PACKAGE
from src.project_base.settings.enums import LogLevel
from src.project_base.settings.models import Logging

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def _non_pytest_handlers(logger: logging.Logger) -> list[logging.Handler]:
    """Return handlers excluding pytest's LogCaptureHandler."""
    return [h for h in logger.handlers if h.__class__.__name__ != "LogCaptureHandler"]


def _redirect_console(logger: logging.Logger) -> io.StringIO:
    """Replace console-handler streams on `logger` with a `StringIO` and return it.

    Only replaces `StreamHandler`s that are not `FileHandler`s or pytest's own handler.
    """
    stream = io.StringIO()
    for handler in logger.handlers:
        if (
            isinstance(handler, logging.StreamHandler)
            and not isinstance(handler, logging.FileHandler)
            and handler.__class__.__name__ != "LogCaptureHandler"
        ):
            handler.stream = stream
    return stream


def _close_file_handlers(logger: logging.Logger) -> None:
    """Flush and close every `FileHandler` on *logger*."""
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.close()


@pytest.fixture(autouse=True)
def _clean_logging_state(tmp_path: Path) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """Reset logging state and redirect log files to a temporary directory."""
    root_logger = logging.getLogger()
    loggers = [root_logger, APP_LOGGER, MODULE_LOGGER]

    def _reset() -> None:
        for _logger in loggers:
            for handler in _logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.close()
            _logger.handlers = [
                h for h in _logger.handlers if h.__class__.__name__ == "LogCaptureHandler"
            ]
            _logger.setLevel(logging.NOTSET)
            _logger.propagate = True

    _reset()

    # Patch the LOGS path and reset the singleton's state
    with patch.object(logging_module, "LOGS", tmp_path / "logs"):
        # Reset the LoggingConfiguration singleton
        logging_module.configure_logging.__self__._is_configured = False
        yield
        logging_module.configure_logging.__self__._is_configured = False

    _reset()


class TestCorrelationIdFormatter:
    """Tests for the CorrelationIdFormatter class."""

    def test_prepends_correlation_id_when_present(self) -> None:
        """Test that the correlation ID is prepended to the message."""
        formatter = CorrelationIdFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Hello",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "abc-123"

        formatted = formatter.format(record)

        assert formatted.endswith("[abc-123] Hello")

    def test_no_prefix_when_correlation_id_absent(self) -> None:
        """Test that the message has no prefix when correlation ID is not set."""
        formatter = CorrelationIdFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Plain message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        assert formatted == "Plain message"

    def test_no_prefix_when_correlation_id_empty(self) -> None:
        """Test that an empty correlation ID does not produce a prefix."""
        formatter = CorrelationIdFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="No ID",
            args=(),
            exc_info=None,
        )
        record.correlation_id = ""

        formatted = formatter.format(record)

        assert formatted == "No ID"

    def test_does_not_mutate_original_record(self) -> None:
        """Test that the original LogRecord is not modified."""
        formatter = CorrelationIdFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Original",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "xyz"

        formatter.format(record)

        assert record.msg == "Original"


class TestConfigureLogging:
    """Tests for the configure_logging function."""

    def test_app_loggers_have_debug_level_and_no_propagation(self) -> None:
        """Test that APP_LOGGER and MODULE_LOGGER are at DEBUG with propagation disabled."""
        config = Logging(log_level=LogLevel.INFO, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        for _logger in (APP_LOGGER, MODULE_LOGGER):
            assert _logger.level == logging.DEBUG
            assert _logger.propagate is False

    def test_root_logger_at_debug_level(self) -> None:
        """Test that the root logger is set to DEBUG."""
        config = Logging(log_level=LogLevel.INFO, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        assert logging.getLogger().level == logging.DEBUG

    def test_app_console_handler_uses_specified_log_level(self) -> None:
        """Test that the app console handler filters at the given log_level."""
        config = Logging(log_level=LogLevel.WARNING, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        stream_handlers: list[logging.Handler] = [
            h
            for h in _non_pytest_handlers(APP_LOGGER)
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) == 1
        assert stream_handlers[0].level == logging.WARNING

    def test_root_console_handler_uses_third_party_level(self) -> None:
        """Test that the root console handler filters at third_party_log_level."""
        config = Logging(log_level=LogLevel.INFO, third_party_log_level=LogLevel.ERROR)
        configure_logging(config)

        root = logging.getLogger()
        stream_handlers: list[logging.Handler] = [
            h
            for h in _non_pytest_handlers(root)
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) == 1
        assert stream_handlers[0].level == logging.ERROR

    def test_file_handler_on_all_loggers_at_debug(self) -> None:
        """Test that a DEBUG-level file handler is attached to all three loggers."""
        config = Logging(log_level=LogLevel.INFO, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        for lgr in (logging.getLogger(), APP_LOGGER, MODULE_LOGGER):
            file_handlers = [
                h for h in _non_pytest_handlers(lgr) if isinstance(h, logging.FileHandler)
            ]
            assert len(file_handlers) >= 1
            assert all(h.level == logging.DEBUG for h in file_handlers)

    def test_correlation_id_filter_on_all_handlers(self) -> None:
        """Test that every handler has a CorrelationIdFilter."""
        config = Logging(log_level=LogLevel.INFO, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        for lgr in (logging.getLogger(), APP_LOGGER, MODULE_LOGGER):
            for handler in _non_pytest_handlers(lgr):
                assert any(isinstance(f, CorrelationIdFilter) for f in handler.filters)

    def test_creates_logs_directory(self, tmp_path: Path) -> None:
        """Test that the logs directory is created during configuration."""
        config = Logging(log_level=LogLevel.INFO, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        assert (tmp_path / "logs").exists()
        assert (tmp_path / "logs").is_dir()

    def test_second_call_warns_and_is_noop(self) -> None:
        """Test that a second call emits a warning and does not add more handlers."""
        config = Logging(log_level=LogLevel.INFO, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)
        handler_count = len(APP_LOGGER.handlers)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            configure_logging(config)

        assert len(caught) == 1
        assert "already configured" in str(caught[0].message).lower()
        assert len(APP_LOGGER.handlers) == handler_count


class TestLoggingOutput:
    """Tests for actual logging output through the configured system."""

    def test_app_log_reaches_console_and_file(self, tmp_path: Path) -> None:
        """Test that an app log message appears in both console stream and log file."""
        config = Logging(log_level=LogLevel.INFO, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        stream = _redirect_console(APP_LOGGER)

        APP_LOGGER.info("visible message")

        assert "visible message" in stream.getvalue()

        _close_file_handlers(APP_LOGGER)
        log_file = tmp_path / "logs" / "app.log"
        assert "visible message" in log_file.read_text()

    def test_console_filters_below_log_level(self, tmp_path: Path) -> None:
        """Test that messages below the log level don't reach the console but do reach the file."""
        config = Logging(log_level=LogLevel.WARNING, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        stream = _redirect_console(APP_LOGGER)

        APP_LOGGER.debug("debug msg")
        APP_LOGGER.info("info msg")
        APP_LOGGER.warning("warning msg")

        output = stream.getvalue()
        assert "debug msg" not in output
        assert "info msg" not in output
        assert "warning msg" in output

        _close_file_handlers(APP_LOGGER)
        log_content = (tmp_path / "logs" / "app.log").read_text()
        assert "debug msg" in log_content
        assert "info msg" in log_content
        assert "warning msg" in log_content

    def test_third_party_log_reaches_root_console(self) -> None:
        """Test that a third-party logger's warning reaches the root console handler."""
        config = Logging(log_level=LogLevel.INFO, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        stream = _redirect_console(logging.getLogger())

        logging.getLogger("some_third_party").warning("3p warning")

        assert "3p warning" in stream.getvalue()


class TestCorrelationIdIntegration:
    """Tests for end-to-end correlation ID behaviour."""

    @pytest.fixture(autouse=True)
    def _reset_correlation_id(self) -> Iterator[None]:
        """Clear the correlation ID context variable around each test."""
        correlation_id.set("")
        yield
        correlation_id.set("")

    def test_correlation_id_in_console_output(self) -> None:
        """Test that the correlation ID is prepended when set."""
        config = Logging(log_level=LogLevel.DEBUG, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        stream = _redirect_console(APP_LOGGER)

        correlation_id.set("req-42")
        APP_LOGGER.info("traced message")

        output = stream.getvalue()
        assert "[req-42]" in output
        assert "traced message" in output

    def test_correlation_id_in_file_output(self, tmp_path: Path) -> None:
        """Test that the correlation ID appears in the log file."""
        config = Logging(log_level=LogLevel.DEBUG, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        correlation_id.set("file-id-7")
        APP_LOGGER.info("file traced")

        _close_file_handlers(APP_LOGGER)
        log_content = (tmp_path / "logs" / "app.log").read_text()
        assert "[file-id-7]" in log_content

    def test_multiple_messages_share_correlation_id(self, tmp_path: Path) -> None:
        """Test that several log messages share the same correlation ID."""
        config = Logging(log_level=LogLevel.DEBUG, third_party_log_level=LogLevel.WARNING)
        configure_logging(config)

        correlation_id.set("shared-99")
        APP_LOGGER.debug("one")
        APP_LOGGER.info("two")
        APP_LOGGER.warning("three")

        _close_file_handlers(APP_LOGGER)
        log_content = (tmp_path / "logs" / "app.log").read_text()
        expected_log_count = 3
        assert log_content.count("[shared-99]") == expected_log_count


class TestWarningsHook:
    """Tests for the LoggingConfiguration._install_warnings_hook static method."""

    @pytest.fixture(autouse=True)
    def _restore_showwarning(self) -> Iterator[None]:
        """Restore warnings.showwarning to its original value after each test."""
        original = warnings.showwarning
        yield
        warnings.showwarning = original

    def test_own_code_warning_routes_to_app_warnings_logger(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that a warning whose filename is inside PACKAGE goes to APP_LOGGER's warnings."""
        LoggingConfiguration._install_warnings_hook()

        with caplog.at_level(logging.WARNING):
            warnings.showwarning(
                UserWarning("own code"),
                UserWarning,
                str(PACKAGE / "some_module.py"),
                lineno=1,
            )

        app_records = [r for r in caplog.records if r.name == APP_LOGGER.getChild("warnings").name]
        assert len(app_records) == 1
        assert "own code" in app_records[0].getMessage()

    def test_third_party_warning_routes_to_py_warnings_logger(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that a warning from outside PACKAGE is routed to the py.warnings logger."""
        LoggingConfiguration._install_warnings_hook()

        with caplog.at_level(logging.WARNING):
            warnings.showwarning(
                UserWarning("third party"),
                UserWarning,
                "/usr/lib/python3/site-packages/some_lib.py",
                lineno=10,
            )

        py_records = [r for r in caplog.records if r.name == "py.warnings"]
        assert len(py_records) == 1
        assert "third party" in py_records[0].getMessage()

    def test_explicit_file_argument_bypasses_logging(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that a non-None file argument bypasses the logging system entirely."""
        with patch("warnings.showwarning") as original_showwarning:
            LoggingConfiguration._install_warnings_hook()

            with caplog.at_level(logging.WARNING):
                warnings.showwarning(
                    UserWarning("file warning"),
                    UserWarning,
                    "anywhere.py",
                    lineno=1,
                    file=io.StringIO(),
                )

        original_showwarning.assert_called_once()

        assert not caplog.records


class TestExceptionHook:
    """Tests for the LoggingConfiguration._install_exception_hook static method."""

    @pytest.fixture(autouse=True)
    def _restore_excepthook(self) -> Iterator[None]:
        """Reset sys.excepthook to the built-in default before each test and restore it after.

        Resetting to sys.__excepthook__ avoids chaining with any hook installed by a prior test's
        configure_logging call (which doesn't get undone by _clean_logging_state).
        """
        sys.excepthook = sys.__excepthook__
        yield
        sys.excepthook = sys.__excepthook__

    def test_uncaught_exception_is_logged_as_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that the hook logs the exception at ERROR level with exc_info."""
        LoggingConfiguration._install_exception_hook()

        with caplog.at_level(logging.ERROR, logger=logging_module.logger.name):
            message = "something went wrong"
            try:
                raise RuntimeError(message)  # noqa: TRY301 necessary for test
            except RuntimeError:
                exc_type, exc_value, exc_tb = sys.exc_info()
                assert exc_type is not None
                assert exc_value is not None
                sys.excepthook(exc_type, exc_value, exc_tb)

        assert any(
            r.levelno == logging.ERROR and "Uncaught exception" in r.getMessage()
            for r in caplog.records
        )

    def test_original_excepthook_is_still_called(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that the original sys.excepthook writes to stderr after the hook is installed."""
        LoggingConfiguration._install_exception_hook()

        message = "test"
        try:
            raise RuntimeError(message)  # noqa: TRY301 necessary for test
        except RuntimeError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            assert exc_type is not None
            assert exc_value is not None
            sys.excepthook(exc_type, exc_value, exc_tb)

        assert "RuntimeError" in capsys.readouterr().err
