"""Unit tests for tenant-aware MCP tool service behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.mcp.service import MCPToolService
from src.models.mcp import MCPInvokeRequest, MCPToolName
from src.models.mindmap import MindMapResponse, MindMapTrace, StageTiming, SynthesisResult
from src.models.schemas import AuditResponse, ContextResponse, FactResponse

EXPECTED_AUDIT_CALLS_WITH_AUTH = 2  # 1 for authorization granted + 1 for operation


class TestMCPToolService:
    """Contract tests for tenant propagation through MCP tools."""

    @pytest.fixture(autouse=True)
    def _stub_record_audit_event(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub audit persistence for tests that do not explicitly patch it.

        This prevents real Spanner calls during unit tests. Tests that need
        to control audit behavior should patch record_audit_event directly.
        """

        async def fake_record_audit_event(**_: object) -> AuditResponse:
            return AuditResponse(
                tenant_id="tenant_a",
                event_id="audit_stub",
                event_type="MCP_AUTHORIZATION_GRANTED",
                timestamp=datetime.now(UTC),
            )

        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI.record_audit_event",
            fake_record_audit_event,
        )

    async def test_memory_search_passes_tenant_to_pipeline(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Search invocations should forward tenant_id into the pipeline boundary."""
        fake_pipeline = AsyncMock()
        fake_pipeline.execute.return_value = self._build_mindmap_response()
        service = MCPToolService(mindmap_pipeline=fake_pipeline)

        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI._increment_session_action_count",
            lambda *_: 1,
        )

        response = await service.invoke(
            MCPInvokeRequest(
                tenant_id="tenant_a",
                session_id="sess_1",
                tool_name=MCPToolName.MEMORY_SEARCH,
                arguments={"query": "what happened?", "session_id": "sess_1"},
                request_id="req_1",
            )
        )

        assert response.success is True
        fake_pipeline.execute.assert_awaited_once_with(
            query="what happened?",
            session_id="sess_1",
            tenant_id="tenant_a",
            authorization_scope=None,
        )

    async def test_memory_search_validation_error_preserves_tenant_request(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validation failures should still return the stable MCP contract."""
        service = MCPToolService(mindmap_pipeline=AsyncMock())

        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI._increment_session_action_count",
            lambda *_: 1,
        )

        response = await service.invoke(
            MCPInvokeRequest(
                tenant_id="tenant_a",
                session_id="sess_1",
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

    async def test_memory_add_fact_passes_tenant_to_memory_api(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fact ingestion should forward tenant_id into the memory API layer."""
        service = MCPToolService(mindmap_pipeline=AsyncMock())

        mock_add = AsyncMock(
            return_value=FactResponse(
                tenant_id="tenant_a",
                entity_id="ent_1",
                entity_type="PERSON",
                node_path="/PERSON/ent_1",
                weight=0.5,
                created_at=datetime.now(UTC),
            )
        )
        monkeypatch.setattr("src.mcp.service.MemoryAPI.add_semantic_fact", mock_add)
        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI._increment_session_action_count", lambda *_: 3
        )

        response = await service.invoke(
            MCPInvokeRequest(
                tenant_id="tenant_a",
                tool_name=MCPToolName.MEMORY_ADD_FACT,
                session_id="sess_1",
                arguments={"entity_type": "PERSON", "entity_id": "ent_1"},
            )
        )

        assert response.success is True
        mock_add.assert_awaited_once_with(
            tenant_id="tenant_a",
            entity_type="PERSON",
            entity_id="ent_1",
            attributes={},
            relationship=None,
            session_id="sess_1",
            authorization_scope=None,
            source_agent_id=None,
            source_query_id=None,
        )

    async def test_memory_log_trace_passes_tenant_to_memory_api(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Trace logging should write audit events under the request tenant."""
        service = MCPToolService(mindmap_pipeline=AsyncMock())

        mock_record = AsyncMock(
            return_value=AuditResponse(
                tenant_id="tenant_a",
                event_id="evt_1",
                event_type="AGENT_REASONING_STEP",
                timestamp=datetime.now(UTC),
            )
        )
        monkeypatch.setattr("src.mcp.service.MemoryAPI.record_audit_event", mock_record)
        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI._increment_session_action_count", lambda *_: 2
        )

        response = await service.invoke(
            MCPInvokeRequest(
                tenant_id="tenant_a",
                tool_name=MCPToolName.MEMORY_LOG_TRACE,
                session_id="sess_1",
                arguments={"decision_context": {"step": "mine"}},
            )
        )

        assert response.success is True
        assert mock_record.await_count == EXPECTED_AUDIT_CALLS_WITH_AUTH
        # Second call should be the actual trace logging
        calls = mock_record.call_args_list
        trace_call = calls[1]
        assert trace_call.kwargs["tenant_id"] == "tenant_a"
        assert trace_call.kwargs["event_type"] == "AGENT_REASONING_STEP"
        assert trace_call.kwargs["source_node_id"] == "sess_1"
        assert trace_call.kwargs["context"] == {"step": "mine"}

    async def test_memory_recall_context_passes_tenant_to_memory_api(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Context recall should be tenant-scoped before reaching the memory API."""
        service = MCPToolService(mindmap_pipeline=AsyncMock())

        mock_recall = AsyncMock(
            return_value=ContextResponse(
                tenant_id="tenant_a",
                session_id="sess_1",
                turns=[],
                total_weight_sum=0.0,
                retrieved_at=datetime.now(UTC),
            )
        )
        monkeypatch.setattr("src.mcp.service.MemoryAPI.retrieve_context_window", mock_recall)
        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI._increment_session_action_count", lambda *_: 2
        )

        response = await service.invoke(
            MCPInvokeRequest(
                tenant_id="tenant_a",
                tool_name=MCPToolName.MEMORY_RECALL_CONTEXT,
                session_id="sess_1",
                arguments={"window_size": 5},
            )
        )

        assert response.success is True
        mock_recall.assert_awaited_once_with(
            tenant_id="tenant_a",
            session_id="sess_1",
            window_size=5,
            authorization_scope=None,
        )

    async def test_audit_write_failure_raises_not_silently_swallowed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Audit write failure must propagate, not be silently absorbed.

        When MemoryAPI.record_audit_event raises, the exception must surface
        to the caller so that security-critical failures are never masked.
        """
        fake_pipeline = AsyncMock()
        fake_pipeline.execute.return_value = self._build_mindmap_response()
        service = MCPToolService(mindmap_pipeline=fake_pipeline)

        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI._increment_session_action_count",
            lambda *_: 1,
        )

        with (
            patch(
                "src.mcp.service.MemoryAPI.record_audit_event",
                side_effect=RuntimeError("spanner down"),
            ),
            pytest.raises(RuntimeError, match="spanner down"),
        ):
            await service.invoke(
                MCPInvokeRequest(
                    tenant_id="tenant_a",
                    session_id="sess_1",
                    tool_name=MCPToolName.MEMORY_SEARCH,
                    arguments={"query": "what happened?", "session_id": "sess_1"},
                    request_id="req_audit_test",
                )
            )

    @staticmethod
    def _build_mindmap_response() -> MindMapResponse:
        """Build a deterministic pipeline response for MCP tests."""
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
