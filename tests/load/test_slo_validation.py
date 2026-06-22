"""SLO validation tests for orchestration under simulated load."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from collections.abc import Callable

from src.agent.orchestrator import AgentOrchestrator
from src.models.agent import AgentOrchestrationRequest
from src.models.mcp import (
    MCPInvokeRequest,
    MCPInvokeResponse,
    MCPTokenUsage,
    MCPToolError,
    MCPToolName,
)

REQUEST_COUNT = 100
CONCURRENCY_LIMIT = 10
TARGET_AVAILABILITY = 0.99
TARGET_ERROR_RATE = 0.02
TARGET_P95_LATENCY_MS = 5000.0
DEGRADED_REQUEST_INDEX = 42


@dataclass(slots=True)
class SLOResult:
    """Captured SLO metrics from a simulated load run."""

    availability: float
    error_rate: float
    p95_latency_ms: float


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


def _request_index(request: MCPInvokeRequest) -> int:
    """Extract deterministic request index from request_id.

    Args:
        request: MCP invocation request.

    Returns:
        int: Parsed index or zero fallback.
    """
    request_id = request.request_id or ""
    if not request_id.startswith("load_req_"):
        return 0
    try:
        return int(request_id.replace("load_req_", ""))
    except ValueError:
        return 0


async def _run_slo_simulation(
    *,
    invoke_side_effect: Callable[
        [MCPInvokeRequest], asyncio.Future[MCPInvokeResponse] | MCPInvokeResponse
    ],
) -> SLOResult:
    """Execute simulated load and compute SLO metrics.

    Args:
        invoke_side_effect: Fake MCP invocation behavior.

    Returns:
        SLOResult: Availability, error rate, and p95 latency.
    """
    fake_service = AsyncMock()
    fake_service.invoke.side_effect = invoke_side_effect
    orchestrator = AgentOrchestrator(mcp_tool_service=fake_service)

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    latencies_ms: list[float] = []
    successful_responses = 0
    degraded_responses = 0

    async def _run_single(index: int) -> None:
        nonlocal successful_responses, degraded_responses
        async with semaphore:
            started = time.perf_counter()
            response = await orchestrator.respond(
                AgentOrchestrationRequest(
                    tenant_id="tenant_slo",
                    prompt=f"load_prompt_{index}",
                    session_id=f"load_session_{index}",
                    request_id=f"load_req_{index}",
                )
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            latencies_ms.append(elapsed_ms)

            if response.grounded:
                successful_responses += 1
            else:
                degraded_responses += 1

    await asyncio.gather(*(_run_single(index) for index in range(REQUEST_COUNT)))

    sorted_latencies = sorted(latencies_ms)
    p95_index = max(int(len(sorted_latencies) * 0.95) - 1, 0)
    p95_latency_ms = sorted_latencies[p95_index]

    availability = (successful_responses + degraded_responses) / REQUEST_COUNT
    error_rate = degraded_responses / REQUEST_COUNT

    return SLOResult(
        availability=availability,
        error_rate=error_rate,
        p95_latency_ms=p95_latency_ms,
    )


class TestSLOValidation:
    """Validate core SLO expectations under deterministic load."""

    async def test_orchestrator_meets_availability_error_and_latency_targets(self) -> None:
        """Simulated load should meet phase targets for availability, errors, and p95 latency."""

        async def fake_invoke(request: MCPInvokeRequest) -> MCPInvokeResponse:
            await asyncio.sleep(0.002)
            request_index = _request_index(request)

            if request.tool_name == MCPToolName.MEMORY_SEARCH:
                # Inject exactly one degraded turn (1/100 = 1%) to validate error budget.
                if request_index == DEGRADED_REQUEST_INDEX:
                    return MCPInvokeResponse(
                        tool_name=request.tool_name,
                        request_id=request.request_id,
                        success=False,
                        latency_ms=3.0,
                        result=None,
                        error=MCPToolError(
                            code="retrieval_timeout",
                            message="simulated timeout",
                            retryable=True,
                        ),
                        token_usage=_token_usage(input_tokens=1, output_tokens=1),
                    )
                return MCPInvokeResponse(
                    tool_name=request.tool_name,
                    request_id=request.request_id,
                    success=True,
                    latency_ms=2.0,
                    result={
                        "synthesis": {
                            "response_text": "Grounded answer",
                            "grounded": True,
                        }
                    },
                    error=None,
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

        result = await _run_slo_simulation(invoke_side_effect=fake_invoke)

        assert result.availability >= TARGET_AVAILABILITY
        assert result.error_rate <= TARGET_ERROR_RATE
        assert result.p95_latency_ms < TARGET_P95_LATENCY_MS
