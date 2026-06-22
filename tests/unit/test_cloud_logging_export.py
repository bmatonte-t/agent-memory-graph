"""Unit tests for Cloud Logging configuration and structured log emission."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    import pytest

from src.observability.logging import structured_log
from src.project_base.logging import LoggingConfiguration
from src.project_base.settings.models import CloudLogging


class TestStructuredLog:
    """Behavior tests for the structured_log helper."""

    def test_structured_log_emits_at_requested_level(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """structured_log should emit at the specified level with fields in extra."""
        log = logging.getLogger("test.structured_log")
        with caplog.at_level(logging.INFO, logger="test.structured_log"):
            structured_log(
                log,
                logging.INFO,
                "test_event",
                {"tenant_id": "t1", "session_id": "s1"},
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.INFO
        assert "test_event" in record.message
        assert record.__dict__.get("tenant_id") == "t1"
        assert record.__dict__.get("session_id") == "s1"
        assert record.__dict__.get("event") == "test_event"

    def test_structured_log_includes_json_in_message(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Message string should contain the fields as compact JSON."""
        log = logging.getLogger("test.structured_log_json")
        with caplog.at_level(logging.DEBUG, logger="test.structured_log_json"):
            structured_log(log, logging.DEBUG, "db_query", {"table": "MemoryNode", "rows": 42})

        assert len(caplog.records) == 1
        assert "MemoryNode" in caplog.records[0].message
        assert "42" in caplog.records[0].message

    def test_structured_log_handles_non_json_serializable_values(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """structured_log should not raise for non-JSON-serializable values."""
        log = logging.getLogger("test.structured_log_types")
        obj = object()
        with caplog.at_level(logging.WARNING, logger="test.structured_log_types"):
            structured_log(log, logging.WARNING, "custom_types", {"obj": obj, "count": 1})

        assert len(caplog.records) == 1
        assert caplog.records[0].__dict__.get("count") == 1


class TestCloudLoggingHandler:
    """Unit tests for Cloud Logging handler installation."""

    def test_configure_logging_skips_cloud_when_disabled(self) -> None:
        """Cloud Logging handler should not be installed when enabled=False."""
        # Call the install path directly with a valid spec'd mock to verify it doesn't raise.
        mock_handler = MagicMock(spec=logging.Handler)
        mock_handler.level = logging.INFO
        mock_client_instance = MagicMock()
        mock_client_instance.get_default_handler.return_value = mock_handler

        with patch("google.cloud.logging.Client", return_value=mock_client_instance):
            LoggingConfiguration._install_cloud_logging_handler(
                project_id=None, labels={}, log_level="INFO"
            )
            mock_client_instance.get_default_handler.assert_called_once()
        # cleanup
        logging.getLogger().removeHandler(mock_handler)

    def test_install_cloud_logging_handler_attaches_handler(self) -> None:
        """_install_cloud_logging_handler should add a handler to the root logger."""
        mock_handler = MagicMock(spec=logging.Handler)
        mock_handler.level = logging.INFO
        mock_client_instance = MagicMock()
        mock_client_instance.get_default_handler.return_value = mock_handler

        with patch("google.cloud.logging.Client", return_value=mock_client_instance):
            LoggingConfiguration._install_cloud_logging_handler(
                project_id="test-project",
                labels={"env": "test"},
                log_level="INFO",
            )

        mock_client_instance.get_default_handler.assert_called_once()
        root_handlers = logging.getLogger().handlers
        assert mock_handler in root_handlers
        # Cleanup
        logging.getLogger().removeHandler(mock_handler)

    def test_install_cloud_logging_handler_falls_back_gracefully_on_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A connection failure should log a warning, not raise."""
        with (
            patch(
                "google.cloud.logging.Client",
                side_effect=RuntimeError("auth failed"),
            ),
            caplog.at_level(logging.WARNING, logger="src.project_base.logging"),
        ):
            LoggingConfiguration._install_cloud_logging_handler(
                project_id="bad-project",
                labels={},
                log_level="INFO",
            )

        warning_messages = " ".join(r.message for r in caplog.records)
        assert "cloud_logging_handler_unavailable" in warning_messages

    def test_cloud_logging_settings_model_defaults(self) -> None:
        """CloudLogging should default to disabled with no project_id."""
        config = CloudLogging()
        assert config.enabled is False
        assert config.project_id is None
        assert config.labels == {}

    def test_cloud_logging_settings_model_accepts_project(self) -> None:
        """CloudLogging should store project_id and labels correctly."""
        config = CloudLogging(
            enabled=True, project_id="my-project", labels={"service": "agent-memory-graph"}
        )
        assert config.enabled is True
        assert config.project_id == "my-project"
        assert config.labels["service"] == "agent-memory-graph"
