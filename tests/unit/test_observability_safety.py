"""Observability Safety Tests - Phase 4C

Phase 4C focuses on validating observability (logs, traces, metrics) doesn't leak:
- Sensitive field values (tenant_ids, session_ids, query contents)
- Implementation details (service names, stack traces, schema names)
- User data that shouldn't be observable

STATUS: Hardened validation message checks
Scope: Verify responses and logs avoid leaking sensitive or internal details
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

if TYPE_CHECKING:
    from pytest import LogCaptureFixture

HTTP_UNPROCESSABLE_ENTITY = 422


class TestValidationErrorMessageContent:
    """Validate sanitized request-validation messages for Phase 4C hardening."""

    def test_invalid_tool_name_does_not_expose_valid_tools(self) -> None:
        """Invalid tool validation should not expose internal enum values."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/mcp/invoke",
            json={
                "tenant_id": "tenant_a",
                "tool_name": "invalid_tool",
                "arguments": {},
            },
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        payload = response.json()
        error_message = payload.get("error", "")

        assert "memory_search" not in error_message
        assert "memory_add_fact" not in error_message
        assert "memory_log_trace" not in error_message
        assert "Invalid request payload" in error_message

    def test_validation_error_message_omits_file_and_line_details(
        self, caplog: LogCaptureFixture
    ) -> None:
        """Client validation messages should not include file path or line details."""
        client = TestClient(app)

        with caplog.at_level("INFO"):
            response = client.post(
                "/api/v1/mcp/invoke",
                json={
                    "tenant_id": "tenant_a",
                    "tool_name": "invalid",
                    "arguments": {},
                },
            )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        payload = response.json()
        error_message = payload.get("error", "")

        assert "file" not in error_message.lower()
        assert ".py" not in error_message.lower()
        assert " line " not in error_message.lower()


class TestErrorResponseStructure:
    """Validate error response structure is appropriate for Phase 4C."""

    def test_validation_error_response_format(self) -> None:
        """Validation errors should follow consistent error response format."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/mcp/invoke",
            json={
                "tenant_id": "tenant_a",
                "tool_name": "invalid_tool",
                "arguments": {},
            },
        )

        payload = response.json()

        # Should have error response structure
        assert "error" in payload or "message" in payload
        assert "code" in payload
        assert "timestamp" in payload

        # Response should not echo back request details
        response_text = json.dumps(payload).lower()
        assert "tenant_a" not in response_text or "error" not in response_text.lower()

    def test_error_response_no_full_traceback(self) -> None:
        """Error responses should not include full Python tracebacks."""
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/mcp/invoke",
            json={
                "tenant_id": "tenant_a",
                "tool_name": "invalid_tool",
                "arguments": {},
            },
        )

        payload = response.json()
        response_text = json.dumps(payload)

        # Should not include full Python Traceback
        assert "Traceback" not in response_text


class TestObservabilityBoundaries:
    """Establish observability safety boundaries for Phase 4C."""

    def test_request_fields_validation_provides_meaningful_feedback(self) -> None:
        """Validation errors should help developers fix issues without exposing internals."""
        client = TestClient(app)

        # Test 1: Missing tenant_id
        response = client.post(
            "/api/v1/mcp/invoke",
            json={
                "tool_name": "memory_search",
                "arguments": {},
            },
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        payload = response.json()
        assert "tenant_id" in payload.get("error", "").lower()

    def test_response_headers_are_safe(self) -> None:
        """HTTP response headers should not contain sensitive data."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/mcp/invoke",
            json={
                "tenant_id": "secret-tenant-id",
                "tool_name": "invalid",
                "arguments": {},
            },
        )

        # Check all response headers
        for header_name, header_value in response.headers.items():
            # Headers should not contain tenant IDs
            assert "secret-tenant-id" not in header_value.lower()
            # Headers should not contain request body content
            if "content" in header_name.lower():
                assert "invalid" not in header_value.lower()


class TestLoggingConfigurationSafety:
    """Validate logging system respects observability boundaries."""

    def test_request_validation_logs_include_helpful_context(
        self, caplog: LogCaptureFixture
    ) -> None:
        """Validation error logs should help with debugging without exposing internals."""
        client = TestClient(app)

        with caplog.at_level("WARNING"):
            response = client.post(
                "/api/v1/mcp/invoke",
                json={
                    "tenant_id": "tenant_a",
                    "tool_name": "invalid_tool",
                    "arguments": {},
                },
            )

        # Logs should indicate validation error occurred
        assert len(caplog.records) > 0

    def test_successful_requests_log_minimal_details(self, caplog: LogCaptureFixture) -> None:
        """Request/response logging should not expose raw query text."""
        client = TestClient(app, raise_server_exceptions=False)

        with caplog.at_level("INFO"):
            response = client.post(
                "/api/v1/mcp/invoke",
                json={
                    "tenant_id": "tenant_a",
                    "tool_name": "memory_search",
                    "arguments": {"query": "SELECT * FROM sensitive_table"},
                    "session_id": "session_1",
                },
            )

        response_text = json.dumps(response.json())
        assert "sensitive_table" not in response_text

        for record in caplog.records:
            assert "sensitive_table" not in record.getMessage()


class TestObservabilityGaps:
    """Validate known observability gaps are remediated."""

    def test_validation_error_messages_are_hardened(self) -> None:
        """Validation errors should avoid exposing internal implementation details."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/mcp/invoke",
            json={
                "tenant_id": "tenant_a",
                "tool_name": "invalid_tool",
                "arguments": {},
            },
        )

        payload = response.json()
        error_text = payload.get("error", "")

        gaps: list[str] = []
        if "memory_search" in error_text:
            gaps.append("Validation error exposes valid tool names")
        if "File" in error_text and ".py" in error_text:
            gaps.append("Validation error exposes file paths")
        if "line" in error_text.lower():
            gaps.append("Validation error exposes line numbers")

        assert len(gaps) == 0
