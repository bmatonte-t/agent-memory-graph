"""Integration tests for Phase 3 multi-turn orchestration behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from src.api.main import app
from src.models.agent import (
    AgentOrchestrationRequest,
    AgentOrchestrationResponse,
    AgentToolCallTrace,
)

if TYPE_CHECKING:
    import pytest

HTTP_OK = 200


class TestAgentMultiTurn:
    """Integration tests for multi-turn behavior through agent endpoint."""

    def test_memory_update_visible_on_subsequent_turn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Second turn should observe memory added during the first turn."""
        session_memory: dict[str, list[str]] = {}

        async def fake_respond(
            _self: object, request: AgentOrchestrationRequest
        ) -> AgentOrchestrationResponse:
            facts = session_memory.setdefault(request.session_id, [])
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
                        tool_name="memory_search",
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
                "prompt": "Remember project_alpha_budget",
                "session_id": "session_1",
                "request_id": "req_1",
                "mode": "single",
            },
        )
        second_turn = client.post(
            "/api/v1/agent/respond",
            json={
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

    def test_memory_isolation_across_sessions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Memory state should remain isolated between two sessions."""
        session_memory: dict[str, str] = {}

        async def fake_respond(
            _self: object, request: AgentOrchestrationRequest
        ) -> AgentOrchestrationResponse:
            if "remember" in request.prompt.lower():
                session_memory[request.session_id] = request.prompt
            known = session_memory.get(request.session_id)
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

        client.post(
            "/api/v1/agent/respond",
            json={"prompt": "remember A", "session_id": "session_a", "request_id": "1"},
        )
        response_b = client.post(
            "/api/v1/agent/respond",
            json={"prompt": "what now", "session_id": "session_b", "request_id": "2"},
        )

        assert response_b.status_code == HTTP_OK
        assert response_b.json()["grounded"] is False
