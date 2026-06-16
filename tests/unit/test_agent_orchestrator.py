"""Unit tests for Phase 3 agent orchestration loop."""

from __future__ import annotations

from unittest.mock import AsyncMock

from src.agent.orchestrator import AgentOrchestrator
from src.models.agent import AgentExecutionMode, AgentOrchestrationRequest
from src.models.mcp import (
    MCPInvokeRequest,
    MCPInvokeResponse,
    MCPTokenUsage,
    MCPToolError,
    MCPToolName,
)

EXPECTED_TOOL_CALLS = 3


def _token_usage(input_tokens: int, output_tokens: int) -> MCPTokenUsage:
    """Create token usage payload for mock MCP responses.

    Args:
        input_tokens: Tokens consumed by prompt/input.
        output_tokens: Tokens consumed by completion/output.

    Returns:
        MCPTokenUsage: Structured token usage model.
    """
    return MCPTokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated=True,
    )


class TestAgentOrchestrator:
    """Contract tests for prompt -> tool -> response orchestration."""

    async def test_respond_success_and_request_id_propagation(self) -> None:
        """Orchestrator should pass one request_id through all tool calls."""
        fake_service = AsyncMock()

        seen_request_ids: list[str | None] = []

        async def fake_invoke(request: MCPInvokeRequest) -> MCPInvokeResponse:
            seen_request_ids.append(request.request_id)
            if request.tool_name == MCPToolName.MEMORY_RECALL_CONTEXT:
                return MCPInvokeResponse(
                    tool_name=request.tool_name,
                    request_id=request.request_id,
                    success=True,
                    latency_ms=1.0,
                    result={"session_id": "sess_1", "turns": []},
                    error=None,
                    token_usage=_token_usage(input_tokens=1, output_tokens=1),
                )
            if request.tool_name == MCPToolName.MEMORY_SEARCH:
                return MCPInvokeResponse(
                    tool_name=request.tool_name,
                    request_id=request.request_id,
                    success=True,
                    latency_ms=1.0,
                    result={
                        "synthesis": {
                            "response_text": "Grounded answer",
                            "grounded": True,
                        }
                    },
                    error=None,
                    token_usage=_token_usage(input_tokens=2, output_tokens=3),
                )
            return MCPInvokeResponse(
                tool_name=request.tool_name,
                request_id=request.request_id,
                success=True,
                latency_ms=1.0,
                result={"event_id": "evt_1"},
                error=None,
                token_usage=_token_usage(input_tokens=1, output_tokens=2),
            )

        fake_service.invoke.side_effect = fake_invoke
        orchestrator = AgentOrchestrator(mcp_tool_service=fake_service)

        response = await orchestrator.respond(
            AgentOrchestrationRequest(prompt="What changed?", session_id="sess_1")
        )

        assert response.execution_mode == AgentExecutionMode.SINGLE
        assert response.grounded is True
        assert response.response_text == "Grounded answer"
        assert len(response.tool_calls) == EXPECTED_TOOL_CALLS
        assert all(request_id == response.request_id for request_id in seen_request_ids)
        assert all(tool_call.request_id == response.request_id for tool_call in response.tool_calls)
        assert all((tool_call.total_tokens or 0) >= 0 for tool_call in response.tool_calls)

    async def test_respond_fallback_when_search_fails(self) -> None:
        """Orchestrator should return insufficiency fallback when search fails."""
        fake_service = AsyncMock()

        async def fake_invoke(request: MCPInvokeRequest) -> MCPInvokeResponse:
            if request.tool_name == MCPToolName.MEMORY_SEARCH:
                return MCPInvokeResponse(
                    tool_name=request.tool_name,
                    request_id=request.request_id,
                    success=False,
                    latency_ms=1.0,
                    result=None,
                    error=MCPToolError(
                        code="retrieval_error",
                        message="search failed",
                        retryable=True,
                    ),
                    token_usage=_token_usage(input_tokens=2, output_tokens=2),
                )
            return MCPInvokeResponse(
                tool_name=request.tool_name,
                request_id=request.request_id,
                success=True,
                latency_ms=1.0,
                result={},
                error=None,
                token_usage=_token_usage(input_tokens=1, output_tokens=1),
            )

        fake_service.invoke.side_effect = fake_invoke
        orchestrator = AgentOrchestrator(mcp_tool_service=fake_service)

        response = await orchestrator.respond(
            AgentOrchestrationRequest(prompt="Need evidence", session_id="sess_2")
        )

        assert response.execution_mode == AgentExecutionMode.SINGLE
        assert response.grounded is False
        assert response.response_text == "Insufficient graph evidence."
        assert len(response.tool_calls) == EXPECTED_TOOL_CALLS

    async def test_supervisor_worker_mode_uses_dedicated_orchestration_path(self) -> None:
        """Supervisor-worker mode should execute dedicated path and preserve mode."""
        fake_service = AsyncMock()
        seen_tool_names: list[MCPToolName] = []

        async def fake_invoke(request: MCPInvokeRequest) -> MCPInvokeResponse:
            seen_tool_names.append(request.tool_name)
            return MCPInvokeResponse(
                tool_name=request.tool_name,
                request_id=request.request_id,
                success=True,
                latency_ms=1.0,
                result={"synthesis": {"response_text": "ok", "grounded": True}},
                error=None,
                token_usage=_token_usage(input_tokens=1, output_tokens=1),
            )

        fake_service.invoke.side_effect = fake_invoke
        orchestrator = AgentOrchestrator(mcp_tool_service=fake_service)

        response = await orchestrator.respond(
            AgentOrchestrationRequest(
                prompt="Need worker path",
                session_id="sess_sw",
                mode=AgentExecutionMode.SUPERVISOR_WORKER,
            )
        )

        assert response.execution_mode == AgentExecutionMode.SUPERVISOR_WORKER
        assert response.grounded is True
        assert len(response.tool_calls) == EXPECTED_TOOL_CALLS
        assert seen_tool_names.count(MCPToolName.MEMORY_RECALL_CONTEXT) == 1
        assert seen_tool_names.count(MCPToolName.MEMORY_SEARCH) == 1
        assert seen_tool_names.count(MCPToolName.MEMORY_LOG_TRACE) == 1

    async def test_vertex_mode_without_adapter_falls_back_to_single(self) -> None:
        """Vertex mode should report single execution when adapter is unavailable."""
        fake_service = AsyncMock()

        async def fake_invoke(request: MCPInvokeRequest) -> MCPInvokeResponse:
            return MCPInvokeResponse(
                tool_name=request.tool_name,
                request_id=request.request_id,
                success=True,
                latency_ms=1.0,
                result={"synthesis": {"response_text": "fallback", "grounded": True}},
                error=None,
                token_usage=_token_usage(input_tokens=1, output_tokens=1),
            )

        fake_service.invoke.side_effect = fake_invoke
        orchestrator = AgentOrchestrator(mcp_tool_service=fake_service, vertex_adapter=None)

        response = await orchestrator.respond(
            AgentOrchestrationRequest(
                prompt="Need vertex",
                session_id="sess_vertex",
                mode=AgentExecutionMode.VERTEX,
            )
        )

        assert response.execution_mode == AgentExecutionMode.SINGLE
        assert response.grounded is True
