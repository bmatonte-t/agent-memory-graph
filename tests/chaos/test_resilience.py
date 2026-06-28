"""Chaos and resilience tests for Phase 4 closeout scenarios."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.agent.orchestrator import AgentOrchestrator
from src.memory.mindmap_pipeline import MindMapConfig, MindMapPipeline, MindMapPipelineError
from src.models.agent import AgentOrchestrationRequest
from src.models.mcp import (
    MCPInvokeRequest,
    MCPInvokeResponse,
    MCPTokenUsage,
    MCPToolError,
    MCPToolName,
)
from src.models.mindmap import PipelineErrorCode, PipelineStage
from src.models.schemas import AuditResponse


def _token_usage(input_tokens: int, output_tokens: int) -> MCPTokenUsage:
    """Build token usage payload for mocked MCP responses.

    Args:
        input_tokens: Prompt token count.
        output_tokens: Completion token count.

    Returns:
        MCPTokenUsage: Structured token usage object.
    """
    return MCPTokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated=True,
    )


class TestResilienceScenarios:
    """Validate graceful degradation for common dependency failures."""

    @pytest.fixture(autouse=True)
    def _stub_audit_trace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub audit trace writes so resilience tests do not require Spanner setup."""

        async def fake_record_audit_event(**_: object) -> AuditResponse:
            return AuditResponse(
                tenant_id="tenant_resilience",
                event_id="audit_test",
                event_type="MINDMAP_EXECUTION",
                timestamp=datetime.now(UTC),
            )

        monkeypatch.setattr(
            "src.memory.mindmap_pipeline.MemoryAPI.record_audit_event",
            fake_record_audit_event,
        )

    async def test_orchestrator_returns_insufficient_when_search_times_out(self) -> None:
        """Search timeout should degrade to explicit insufficiency response."""
        fake_service = AsyncMock()

        async def fake_invoke(request: MCPInvokeRequest) -> MCPInvokeResponse:
            if request.tool_name == MCPToolName.MEMORY_SEARCH:
                return MCPInvokeResponse(
                    tool_name=request.tool_name,
                    request_id=request.request_id,
                    success=False,
                    latency_ms=10.0,
                    result=None,
                    error=MCPToolError(
                        code="retrieval_timeout",
                        message="search timeout",
                        retryable=True,
                    ),
                    token_usage=_token_usage(input_tokens=1, output_tokens=1),
                )
            return MCPInvokeResponse(
                tool_name=request.tool_name,
                request_id=request.request_id,
                success=True,
                latency_ms=2.0,
                result={},
                error=None,
                token_usage=_token_usage(input_tokens=1, output_tokens=1),
            )

        fake_service.invoke.side_effect = fake_invoke
        orchestrator = AgentOrchestrator(mcp_tool_service=fake_service)

        response = await orchestrator.respond(
            AgentOrchestrationRequest(
                tenant_id="tenant_resilience",
                prompt="Explain unavailable dependency",
                session_id="session_resilience",
                request_id="req_resilience",
            )
        )

        assert response.grounded is False
        assert response.response_text == "Insufficient graph evidence."

    async def test_mindmap_returns_explicit_insufficient_when_no_evidence(self) -> None:
        """No-evidence queries must fail safely without hallucinated content."""
        pipeline = MindMapPipeline()

        response = await pipeline.execute(query="?")

        assert response.synthesis.response_text == MindMapPipeline.INSUFFICIENT_EVIDENCE_RESPONSE
        assert response.synthesis.claim_fact_ids == []
        assert response.synthesis.grounded is True

    async def test_mindmap_surfaces_retrieval_error_when_spanner_is_unavailable(self) -> None:
        """Spanner aggregation unavailability should raise retrieval-stage pipeline error."""
        pipeline = MindMapPipeline(config=MindMapConfig(use_spanner_aggregation=True))

        with (
            patch(
                "src.memory.mindmap_pipeline.SpannerClient.execute_sql",
                side_effect=RuntimeError("SpannerClient not initialized. Call initialize() first."),
            ),
            pytest.raises(MindMapPipelineError, match="spanner retrieval unavailable") as error,
        ):
            await pipeline.execute(query="Explain dependency graph")

        assert error.value.stage == PipelineStage.AGGREGATE
        assert error.value.code == PipelineErrorCode.RETRIEVAL_ERROR
