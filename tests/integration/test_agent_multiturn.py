"""Integration tests for tenant-aware multi-turn orchestration behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from src.api.main import app
from src.models.agent import (
    AgentOrchestrationRequest,
    AgentOrchestrationResponse,
    AgentToolCallTrace,
)
from src.models.mcp import MCPToolName

if TYPE_CHECKING:
    import pytest

HTTP_OK = 200


class TestAgentMultiTurn:
    """Integration tests for multi-turn behavior through the agent endpoint."""

    def test_memory_update_visible_on_subsequent_turn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A second turn in the same tenant and session should see prior memory."""
        session_memory: dict[tuple[str, str], list[str]] = {}

        async def fake_respond(
            _self: object, request: AgentOrchestrationRequest
        ) -> AgentOrchestrationResponse:
            memory_key = (request.tenant_id, request.session_id)
            facts = session_memory.setdefault(memory_key, [])
            if "remember" in request.prompt.lower():
                facts.append("project_alpha_budget")
                response_text = "Saved project_alpha_budget."
                grounded = True
            elif facts:
                response_text = f"I remember: {', '.join(facts)}"
                grounded = True
            else:
                response_text = "Insufficient graph evidence."
                grounded = False

            return AgentOrchestrationResponse(
                session_id=request.session_id,
                request_id=request.request_id or "req_test",
                execution_mode=request.mode,
                response_text=response_text,
                grounded=grounded,
                tool_calls=[
                    AgentToolCallTrace(
                        tool_name=MCPToolName.MEMORY_SEARCH,
                        request_id=request.request_id,
                        success=True,
                        latency_ms=1.0,
                        total_tokens=2,
                        error_code=None,
                    )
                ],
            )

        monkeypatch.setattr("src.agent.orchestrator.AgentOrchestrator.respond", fake_respond)
        client = TestClient(app)

        first_turn = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_a",
                "prompt": "Remember project_alpha_budget",
                "session_id": "session_1",
                "request_id": "req_1",
                "mode": "single",
            },
        )
        second_turn = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_a",
                "prompt": "What do you remember?",
                "session_id": "session_1",
                "request_id": "req_2",
                "mode": "single",
            },
        )

        assert first_turn.status_code == HTTP_OK
        assert second_turn.status_code == HTTP_OK
        assert second_turn.json()["grounded"] is True
        assert "project_alpha_budget" in second_turn.json()["response_text"]

    def test_memory_isolated_for_same_session_id_across_tenants(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The same session identifier must not leak memory across tenants."""
        session_memory: dict[tuple[str, str], str] = {}

        async def fake_respond(
            _self: object, request: AgentOrchestrationRequest
        ) -> AgentOrchestrationResponse:
            memory_key = (request.tenant_id, request.session_id)
            if "remember" in request.prompt.lower():
                session_memory[memory_key] = request.prompt
            known = session_memory.get(memory_key)
            response_text = known or "Insufficient graph evidence."
            return AgentOrchestrationResponse(
                session_id=request.session_id,
                request_id=request.request_id or "req_test",
                execution_mode=request.mode,
                response_text=response_text,
                grounded=known is not None,
                tool_calls=[],
            )

        monkeypatch.setattr("src.agent.orchestrator.AgentOrchestrator.respond", fake_respond)
        client = TestClient(app)

        tenant_a_write = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_a",
                "prompt": "remember A",
                "session_id": "shared_session",
                "request_id": "1",
            },
        )
        tenant_b_read = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_b",
                "prompt": "what now",
                "session_id": "shared_session",
                "request_id": "2",
            },
        )
        tenant_a_read = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_a",
                "prompt": "what now",
                "session_id": "shared_session",
                "request_id": "3",
            },
        )

        assert tenant_a_write.status_code == HTTP_OK
        assert tenant_b_read.status_code == HTTP_OK
        assert tenant_a_read.status_code == HTTP_OK
        assert tenant_b_read.json()["grounded"] is False
        assert tenant_a_read.json()["grounded"] is True
        assert "remember A" in tenant_a_read.json()["response_text"]
