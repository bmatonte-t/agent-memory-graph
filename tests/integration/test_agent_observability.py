"""Integration tests for observability and request tracing in Phase 3."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from src.agent.orchestrator import AgentOrchestrator
from src.mcp import service as mcp_module
from src.mcp.service import MCPToolService
from src.models.agent import AgentOrchestrationRequest

if TYPE_CHECKING:
    import pytest


class TestAgentObservability:
    """Observability tests for request ID propagation and telemetry logs."""

    async def test_request_id_propagates_through_tool_chain(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Request IDs should appear in orchestrator and MCP log records."""

        class FakePipeline:
            async def execute(self, query: str, session_id: str | None) -> object:
                return type(
                    "MindMapResponseStub",
                    (),
                    {
                        "model_dump": lambda self, mode: {
                            "query": query,
                            "synthesis": {"response_text": "ok", "grounded": True},
                        }
                    },
                )()

        mcp_service = MCPToolService(mindmap_pipeline=FakePipeline())

        async def fake_add_fact(*args: object, **kwargs: object) -> object:
            return {"fact_id": "not_used"}

        monkeypatch.setattr(mcp_module.MemoryAPI, "add_semantic_fact", fake_add_fact)
        monkeypatch.setattr(
            mcp_module.MemoryAPI,
            "record_audit_event",
            AsyncMock(
                return_value=type(
                    "AuditResponseStub", (), {"model_dump": lambda self, mode: {"event_id": "e1"}}
                )()
            ),
        )
        monkeypatch.setattr(
            mcp_module.MemoryAPI,
            "retrieve_context_window",
            AsyncMock(
                return_value=type(
                    "ContextResponseStub", (), {"model_dump": lambda self, mode: {"turns": []}}
                )()
            ),
        )

        orchestrator = AgentOrchestrator(mcp_tool_service=mcp_service)

        caplog.set_level(logging.INFO)
        request_id = "request_obs_1"
        response = await orchestrator.respond(
            AgentOrchestrationRequest(
                prompt="hello",
                session_id="session_obs",
                request_id=request_id,
            )
        )

        assert response.request_id == request_id
        assert all(tool_call.request_id == request_id for tool_call in response.tool_calls)

        combined_logs = "\n".join(record.getMessage() for record in caplog.records)
        assert "agent_orchestration_start" in combined_logs
        assert "mcp_tool_invoke_start" in combined_logs
        assert request_id in combined_logs

        # Validate logged payloads are JSON and include expected trace fields.
        start_records = [
            record
            for record in caplog.records
            if "agent_orchestration_start" in record.getMessage()
        ]
        assert start_records
        payload_text = (
            start_records[0].getMessage().split("agent_orchestration_start ", maxsplit=1)[1]
        )
        payload = json.loads(payload_text)
        assert payload["request_id"] == request_id
