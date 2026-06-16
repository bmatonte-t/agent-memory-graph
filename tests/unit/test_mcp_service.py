"""Unit tests for Phase 3 MCP tool service."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.mcp.service import MCPToolService
from src.models.mcp import MCPInvokeRequest, MCPToolName
from src.models.mindmap import MindMapTrace, StageTiming, SynthesisResult
from src.models.schemas import AuditResponse, ContextResponse, FactResponse


class TestMCPToolService:
    """Contract tests for MCP tool invocations."""

    @pytest.mark.asyncio
    async def test_memory_search_success(self) -> None:
        """memory_search returns serialized pipeline response."""
        fake_pipeline = AsyncMock()
        fake_pipeline.execute.return_value = self._build_mindmap_response()

        service = MCPToolService(mindmap_pipeline=fake_pipeline)

        response = await service.invoke(
            MCPInvokeRequest(
                tool_name=MCPToolName.MEMORY_SEARCH,
                arguments={"query": "what happened?", "session_id": "sess_1"},
                request_id="req_1",
            )
        )

        assert response.success is True
        assert response.request_id == "req_1"
        assert response.error is None
        assert response.token_usage is not None
        assert response.token_usage.total_tokens >= 0
        assert response.result is not None
        assert response.result["query"] == "what happened?"

    @pytest.mark.asyncio
    async def test_memory_search_validation_error(self) -> None:
        """memory_search requires a non-empty query."""
        fake_pipeline = AsyncMock()
        service = MCPToolService(mindmap_pipeline=fake_pipeline)

        response = await service.invoke(
            MCPInvokeRequest(
                tool_name=MCPToolName.MEMORY_SEARCH,
                arguments={"query": "   "},
                request_id="req_2",
            )
        )

        assert response.success is False
        assert response.request_id == "req_2"
        assert response.error is not None
        assert response.error.code == "validation_error"
        assert response.token_usage is not None
        assert response.token_usage.total_tokens >= 0

    @pytest.mark.asyncio
    async def test_memory_add_fact_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """memory_add_fact delegates to MemoryAPI and returns normalized payload."""
        fake_pipeline = AsyncMock()
        service = MCPToolService(mindmap_pipeline=fake_pipeline)

        mock_add = AsyncMock(
            return_value=FactResponse(
                entity_id="ent_1",
                entity_type="PERSON",
                node_path="/PERSON/ent_1",
                weight=0.5,
                created_at=datetime.now(UTC),
            )
        )
        monkeypatch.setattr("src.mcp.service.MemoryAPI.add_semantic_fact", mock_add)

        response = await service.invoke(
            MCPInvokeRequest(
                tool_name=MCPToolName.MEMORY_ADD_FACT,
                arguments={"entity_type": "PERSON", "entity_id": "ent_1"},
            )
        )

        assert response.success is True
        assert response.error is None
        assert response.result is not None
        assert response.result["entity_id"] == "ent_1"

    @pytest.mark.asyncio
    async def test_memory_log_trace_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """memory_log_trace writes an audit event."""
        fake_pipeline = AsyncMock()
        service = MCPToolService(mindmap_pipeline=fake_pipeline)

        mock_record = AsyncMock(
            return_value=AuditResponse(
                event_id="evt_1",
                event_type="AGENT_REASONING_STEP",
                timestamp=datetime.now(UTC),
            )
        )
        monkeypatch.setattr("src.mcp.service.MemoryAPI.record_audit_event", mock_record)

        response = await service.invoke(
            MCPInvokeRequest(
                tool_name=MCPToolName.MEMORY_LOG_TRACE,
                session_id="sess_1",
                arguments={"decision_context": {"step": "mine"}},
            )
        )

        assert response.success is True
        assert response.result is not None
        assert response.result["event_id"] == "evt_1"

    @pytest.mark.asyncio
    async def test_memory_recall_context_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """memory_recall_context returns context turns."""
        fake_pipeline = AsyncMock()
        service = MCPToolService(mindmap_pipeline=fake_pipeline)

        mock_recall = AsyncMock(
            return_value=ContextResponse(
                session_id="sess_1",
                turns=[],
                total_weight_sum=0.0,
                retrieved_at=datetime.now(UTC),
            )
        )
        monkeypatch.setattr("src.mcp.service.MemoryAPI.retrieve_context_window", mock_recall)

        response = await service.invoke(
            MCPInvokeRequest(
                tool_name=MCPToolName.MEMORY_RECALL_CONTEXT,
                session_id="sess_1",
                arguments={"window_size": 5},
            )
        )

        assert response.success is True
        assert response.result is not None
        assert response.result["session_id"] == "sess_1"

    @staticmethod
    def _build_mindmap_response():
        from src.models.mindmap import MindMapResponse

        return MindMapResponse(
            query="what happened?",
            synthesis=SynthesisResult(
                response_text="Grounded answer",
                claim_fact_ids=["fact_1"],
                grounded=True,
                latency_ms=1.0,
            ),
            trace=MindMapTrace(
                trace_id="trace_1",
                mined_entities=["entity_1"],
                path_ids=["path_1"],
                fact_ids=["fact_1"],
                stage_timings=[StageTiming(stage="mine", latency_ms=1.0)],
                created_at=datetime.now(UTC),
            ),
        )
