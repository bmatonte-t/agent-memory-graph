"""Unit tests for MCP API endpoint contracts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app


class TestMCPApi:
    """HTTP contract tests for MCP invocation endpoint."""

    def test_invoke_endpoint_calls_tool_service(self, monkeypatch) -> None:
        """Endpoint should return normalized tool response from service."""
        from src.models.mcp import MCPInvokeResponse, MCPToolName

        async def fake_invoke(_self, _request):
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
                "tool_name": "memory_search",
                "arguments": {"query": "hello"},
                "session_id": "sess_1",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["tool_name"] == "memory_search"
        assert payload["success"] is True
        assert payload["result"]["ok"] is True

    def test_invoke_endpoint_rejects_unknown_tool_name(self) -> None:
        """Endpoint request validation should reject unknown tool names."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/mcp/invoke",
            json={"tool_name": "unknown_tool", "arguments": {}},
        )

        assert response.status_code == 422
