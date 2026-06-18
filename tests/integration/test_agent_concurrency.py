"""Integration load tests for concurrent agent sessions."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from src.agent.orchestrator import AgentOrchestrator
from src.models.agent import AgentOrchestrationRequest
from src.models.mcp import MCPInvokeRequest, MCPInvokeResponse, MCPToolName

P95_LATENCY_TARGET_MS = 250.0


class TestAgentConcurrency:
    """Concurrency and p95 latency tests for orchestration layer."""

    @pytest.mark.asyncio
    async def test_concurrent_agent_sessions_p95_latency(self) -> None:
        """Concurrent sessions should complete within an acceptable p95 latency."""
        fake_service = AsyncMock()

        async def fake_invoke(request: MCPInvokeRequest) -> MCPInvokeResponse:
            await asyncio.sleep(0.002)
            result = {}
            if request.tool_name == MCPToolName.MEMORY_SEARCH:
                result = {
                    "synthesis": {
                        "response_text": "Grounded answer",
                        "grounded": True,
                    }
                }
            return MCPInvokeResponse(
                tool_name=request.tool_name,
                request_id=request.request_id,
                success=True,
                latency_ms=2.0,
                result=result,
                error=None,
                token_usage={
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                    "estimated": True,
                },
            )

        fake_service.invoke.side_effect = fake_invoke
        orchestrator = AgentOrchestrator(mcp_tool_service=fake_service)

        latencies_ms: list[float] = []

        async def run_session(index: int) -> None:
            started = time.perf_counter()
            response = await orchestrator.respond(
                AgentOrchestrationRequest(
                    prompt=f"prompt_{index}",
                    session_id=f"session_{index}",
                    request_id=f"request_{index}",
                )
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            latencies_ms.append(elapsed_ms)
            assert response.grounded is True

        await asyncio.gather(*(run_session(index) for index in range(30)))

        sorted_latencies = sorted(latencies_ms)
        p95_index = max(int(len(sorted_latencies) * 0.95) - 1, 0)
        p95_latency = sorted_latencies[p95_index]

        assert p95_latency < P95_LATENCY_TARGET_MS
