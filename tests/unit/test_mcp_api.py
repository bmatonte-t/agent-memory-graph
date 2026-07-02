"""Unit tests for MCP API endpoint contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from src.api.main import app
from src.models.mcp import MCPInvokeRequest, MCPInvokeResponse, MCPToolName

if TYPE_CHECKING:
    import pytest

HTTP_OK = 200
HTTP_UNPROCESSABLE_ENTITY = 422
HTTP_BAD_REQUEST = 400


class TestMCPApi:
    """HTTP contract tests for MCP invocation endpoint."""

    def test_invoke_endpoint_calls_tool_service(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Endpoint should return normalized tool response from service."""

        async def fake_invoke(_self: object, _request: MCPInvokeRequest) -> MCPInvokeResponse:
            return MCPInvokeResponse(
                tool_name=MCPToolName.MEMORY_SEARCH,
                success=True,
                latency_ms=1.5,
                result={"ok": True},
                error=None,
            )

        monkeypatch.setattr("src.mcp.service.MCPToolService.invoke", fake_invoke)
        client = TestClient(app)

        response = client.post(
            "/api/v1/mcp/invoke",
            json={
                "tenant_id": "tenant_a",
                "tool_name": "memory_search",
                "arguments": {"query": "hello"},
                "session_id": "sess_1",
            },
        )

        assert response.status_code == HTTP_OK
        payload = response.json()
        assert payload["tool_name"] == "memory_search"
        assert payload["success"] is True
        assert payload["result"]["ok"] is True

    def test_invoke_endpoint_rejects_unknown_tool_name(self) -> None:
        """Endpoint request validation should reject unknown tool names."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/mcp/invoke",
            json={"tenant_id": "tenant_a", "tool_name": "unknown_tool", "arguments": {}},
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_discovery_endpoint_returns_versioned_manifest(self) -> None:
        """Discovery endpoint should return a versioned manifest with tool catalog."""
        client = TestClient(app)

        response = client.get("/.well-known/mcp")

        assert response.status_code == HTTP_OK
        payload = response.json()
        assert payload["manifest_version"] == "1.0"
        assert payload["requested_version"] == "1.0"
        assert "1.0" in payload["supported_versions"]
        assert payload["invoke_endpoint"] == "/api/v1/mcp/invoke"
        assert len(payload["tools"]) >= 1
        assert len(payload["tool_catalog"]) == len(payload["tools"])
        tool_names = {tool["name"] for tool in payload["tools"]}
        assert "memory_search" in tool_names
        assert "memory_add_fact" in tool_names

    def test_discovery_endpoint_accepts_backward_compatible_version_alias(self) -> None:
        """Discovery endpoint should normalize major-only alias for backward compatibility."""
        client = TestClient(app)

        response = client.get("/.well-known/mcp", params={"version": "1"})

        assert response.status_code == HTTP_OK
        payload = response.json()
        assert payload["requested_version"] == "1.0"

    def test_discovery_endpoint_rejects_unsupported_version(self) -> None:
        """Discovery endpoint should reject unsupported major versions."""
        client = TestClient(app)

        response = client.get("/.well-known/mcp", params={"version": "2.0"})

        assert response.status_code == HTTP_BAD_REQUEST
        payload = response.json()
        assert "unsupported discovery version" in payload["detail"]
