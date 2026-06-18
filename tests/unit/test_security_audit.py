"""Security audit tests for API boundary hardening and error redaction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from src.api.main import app

if TYPE_CHECKING:
    import pytest

HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_UNPROCESSABLE_ENTITY = 422
HTTP_INTERNAL_SERVER_ERROR = 500


class TestSecurityAudit:
    """Security-focused tests for boundary validation and safe error behavior."""

    def test_agent_endpoint_redacts_runtime_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Runtime failures must not leak internal exception messages to clients."""

        async def fake_respond(*_: object, **__: object) -> object:
            raise RuntimeError("spanner password leaked")

        monkeypatch.setattr("src.agent.orchestrator.AgentOrchestrator.respond", fake_respond)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_a",
                "prompt": "hello",
                "session_id": "session_1",
            },
        )

        assert response.status_code == HTTP_INTERNAL_SERVER_ERROR
        payload = response.json()
        assert payload["code"] == "RUNTIME_ERROR"
        assert payload["error"] == "An internal error occurred."
        assert "password" not in payload["error"].lower()

    def test_mcp_endpoint_redacts_unhandled_exceptions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unexpected exceptions must not expose implementation details to clients."""

        async def fake_invoke(*_: object, **__: object) -> object:
            raise Exception("stack trace internals leaked")

        monkeypatch.setattr("src.mcp.service.MCPToolService.invoke", fake_invoke)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/mcp/invoke",
            json={
                "tenant_id": "tenant_a",
                "tool_name": "memory_search",
                "arguments": {"query": "hello"},
                "session_id": "session_1",
            },
        )

        assert response.status_code == HTTP_INTERNAL_SERVER_ERROR
        payload = response.json()
        assert payload["code"] == "INTERNAL_ERROR"
        assert payload["error"] == "An unexpected internal error occurred."
        assert "stack" not in payload["error"].lower()
        assert "internals" not in payload["error"].lower()

    def test_permission_errors_map_to_forbidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Permission failures should map to 403 without leaking backend details."""

        async def fake_respond(*_: object, **__: object) -> object:
            raise PermissionError("audit events immutable backend detail")

        monkeypatch.setattr("src.agent.orchestrator.AgentOrchestrator.respond", fake_respond)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_a",
                "prompt": "hello",
                "session_id": "session_1",
            },
        )

        assert response.status_code == HTTP_FORBIDDEN
        payload = response.json()
        assert payload["code"] == "FORBIDDEN"
        assert payload["error"] == "The requested operation is not permitted."
        assert "immutable" not in payload["error"].lower()

    def test_request_validation_rejects_missing_tenant_id(self) -> None:
        """Boundary validation should reject missing required tenant context."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/agent/respond",
            json={
                "prompt": "hello",
                "session_id": "session_1",
            },
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        payload = response.json()
        assert payload["code"] == "REQUEST_VALIDATION_ERROR"
        assert "tenant_id" in payload["error"]

    def test_validation_errors_preserve_safe_client_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Client validation failures should return stable, non-stacktrace responses."""

        async def fake_respond(*_: object, **__: object) -> object:
            raise ValueError("tenant_id cannot be blank")

        monkeypatch.setattr("src.agent.orchestrator.AgentOrchestrator.respond", fake_respond)
        client = TestClient(app)

        response = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_a",
                "prompt": "hello",
                "session_id": "session_1",
            },
        )

        assert response.status_code == HTTP_BAD_REQUEST
        payload = response.json()
        assert payload["code"] == "VALIDATION_ERROR"
        assert payload["error"] == "tenant_id cannot be blank"
        assert "traceback" not in payload["error"].lower()


class TestBoundaryViolationPrevention:
    """Tests that enforce tenant isolation and prevent cross-boundary access."""

    def test_agent_endpoint_rejects_empty_tenant_id(self) -> None:
        """Empty tenant_id should be rejected at boundary."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "",
                "prompt": "hello",
                "session_id": "session_1",
            },
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        payload = response.json()
        assert payload["code"] == "REQUEST_VALIDATION_ERROR"

    def test_agent_endpoint_rejects_null_tenant_id(self) -> None:
        """Null tenant_id should be rejected at boundary."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": None,
                "prompt": "hello",
                "session_id": "session_1",
            },
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        payload = response.json()
        assert payload["code"] == "REQUEST_VALIDATION_ERROR"


class TestInputValidation:
    """Tests for input boundary validation without service invocation."""

    def test_agent_endpoint_rejects_missing_prompt_field(self) -> None:
        """Request without prompt field should fail validation."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_a",
                "session_id": "session_1",
            },
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        payload = response.json()
        assert payload["code"] == "REQUEST_VALIDATION_ERROR"

    def test_agent_endpoint_rejects_missing_session_id_field(self) -> None:
        """Request without session_id field should fail validation."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_a",
                "prompt": "hello",
            },
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        payload = response.json()
        assert payload["code"] == "REQUEST_VALIDATION_ERROR"

    def test_agent_endpoint_rejects_empty_prompt(self) -> None:
        """Empty prompt should be rejected by Pydantic validation."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_a",
                "prompt": "",
                "session_id": "session_1",
            },
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        payload = response.json()
        assert payload["code"] == "REQUEST_VALIDATION_ERROR"

    def test_mcp_endpoint_rejects_missing_tool_name(self) -> None:
        """MCP invoke without tool_name should fail validation."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/mcp/invoke",
            json={
                "tenant_id": "tenant_a",
                "arguments": {"query": "hello"},
                "session_id": "session_1",
            },
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
        payload = response.json()
        assert payload["code"] == "REQUEST_VALIDATION_ERROR"


class TestAuditImmutability:
    """Tests that verify audit event immutability and PermissionError enforcement."""

    def test_permission_error_on_audit_mutation_attempt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Attempts to mutate audit records should result in 403 FORBIDDEN."""

        async def fake_invoke(*_: object, **__: object) -> object:
            raise PermissionError("Cannot update AUDIT_EVENTS: append-only constraint violation")

        monkeypatch.setattr("src.mcp.service.MCPToolService.invoke", fake_invoke)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/mcp/invoke",
            json={
                "tenant_id": "tenant_a",
                "tool_name": "memory_log_trace",
                "arguments": {"decision_context": "test"},
                "session_id": "session_1",
            },
        )

        assert response.status_code == HTTP_FORBIDDEN
        payload = response.json()
        assert payload["code"] == "FORBIDDEN"
        assert "update" not in payload["error"].lower()
        assert "append" not in payload["error"].lower()
