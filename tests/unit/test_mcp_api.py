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
