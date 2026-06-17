"""Unit tests for Phase 3 agent orchestration API endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from src.api.main import app
from src.models.agent import (
    AgentExecutionMode,
    AgentOrchestrationRequest,
    AgentOrchestrationResponse,
    AgentToolCallTrace,
)

if TYPE_CHECKING:
    import pytest

HTTP_OK = 200
HTTP_UNPROCESSABLE_ENTITY = 422


class TestAgentApi:
    """HTTP contract tests for agent orchestration endpoint."""

    def test_agent_respond_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Endpoint should return orchestrated response payload."""

        async def fake_respond(
            _self: object, request: AgentOrchestrationRequest
        ) -> AgentOrchestrationResponse:
            return AgentOrchestrationResponse(
                session_id=request.session_id,
                request_id=request.request_id or "req_123",
                execution_mode=AgentExecutionMode.SINGLE,
                response_text="Grounded answer",
                grounded=True,
                tool_calls=[
                    AgentToolCallTrace(
                        tool_name="memory_search",
                        success=True,
                        latency_ms=1.0,
                        error_code=None,
                    )
                ],
            )

        monkeypatch.setattr("src.agent.orchestrator.AgentOrchestrator.respond", fake_respond)

        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/respond",
            json={"prompt": "hello", "session_id": "sess_1", "request_id": "req_1"},
        )

        assert response.status_code == HTTP_OK
        payload = response.json()
        assert payload["session_id"] == "sess_1"
        assert payload["request_id"] == "req_1"
        assert payload["execution_mode"] == "single"
        assert payload["grounded"] is True

    def test_agent_respond_rejects_empty_prompt(self) -> None:
        """Endpoint validation should reject empty prompts."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/respond",
            json={"prompt": "", "session_id": "sess_1"},
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
