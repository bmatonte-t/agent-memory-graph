"""Integration tests for observability and request tracing in Phase 3."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import src.memory.api as memory_api
from src.agent.orchestrator import AgentOrchestrator
from src.mcp.service import MCPToolService
from src.models.agent import AgentOrchestrationRequest

if TYPE_CHECKING:
    import pytest


class TestAgentObservability:
    """Observability tests for request ID propagation and telemetry logs."""

    async def test_request_id_propagates_through_tool_chain(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Request IDs should appear in orchestrator and MCP log records."""

        class FakePipeline:
            async def execute(
                self,
                query: str,
                session_id: str | None,
                tenant_id: str | None = None,
                authorization_scope: object | None = None,
            ) -> object:
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

        class AuditResponseStub:
            def model_dump(self, mode: str) -> dict[str, str]:
                _ = mode
                return {"event_id": "e1"}

        class ContextResponseStub:
            def model_dump(self, mode: str) -> dict[str, list[object]]:
                _ = mode
                return {"turns": []}

        async def fake_add_fact(*args: object, **kwargs: object) -> object:
            _ = args, kwargs
            return {"fact_id": "not_used"}

        async def fake_record_audit_event(*args: object, **kwargs: object) -> AuditResponseStub:
            _ = args, kwargs
            return AuditResponseStub()

        async def fake_retrieve_context_window(
            *args: object,
            **kwargs: object,
        ) -> ContextResponseStub:
            _ = args, kwargs
            return ContextResponseStub()

        memory_api_class = memory_api.MemoryAPI
        original_add_fact = memory_api_class.add_semantic_fact
        original_record_audit_event = memory_api_class.record_audit_event
        original_retrieve_context_window = memory_api_class.retrieve_context_window
        original_increment_action_count = memory_api_class._increment_session_action_count

        try:
            memory_api_class.add_semantic_fact = fake_add_fact
            memory_api_class.record_audit_event = fake_record_audit_event
            memory_api_class.retrieve_context_window = fake_retrieve_context_window
            memory_api_class._increment_session_action_count = lambda *_: None

            orchestrator = AgentOrchestrator(mcp_tool_service=mcp_service)

            caplog.set_level(logging.INFO)
            request_id = "request_obs_1"
            response = await orchestrator.respond(
                AgentOrchestrationRequest(
                    tenant_id="tenant_obs",
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
        finally:
            memory_api_class.add_semantic_fact = original_add_fact
            memory_api_class.record_audit_event = original_record_audit_event
            memory_api_class.retrieve_context_window = original_retrieve_context_window
            memory_api_class._increment_session_action_count = original_increment_action_count
