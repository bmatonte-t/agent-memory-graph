"""Unit tests for SLI metrics emission across the agent pipeline.

Validates that metric instruments exist, are callable, and that emission calls
propagate correct labels through the orchestrator, MCP service, and MindMap
pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from src.agent.orchestrator import AgentOrchestrator
from src.mcp.service import MCPToolService
from src.memory.mindmap_pipeline import MindMapPipeline
from src.models.agent import AgentOrchestrationRequest
from src.models.mcp import (
    MCPInvokeRequest,
    MCPInvokeResponse,
    MCPTokenUsage,
    MCPToolName,
)
from src.models.schemas import AuditResponse
from src.observability.metrics import (
    configure_metrics,
    mcp_tool_error_counter,
    mcp_tool_invocation_counter,
    orchestrator_request_counter,
    pipeline_execution_histogram,
    pipeline_fact_counter,
)


@pytest.fixture(autouse=True)
def _configure_test_metrics() -> MeterProvider:
    """Configure a test MeterProvider with in-memory reader for each test.

    Returns:
        MeterProvider: Active provider with in-memory reader.
    """
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    from opentelemetry import metrics  # noqa: PLC0415

    metrics.set_meter_provider(provider)
    # Clear the lru_cache so _get_meter() picks up the new provider.
    from src.observability import metrics as obs_metrics  # noqa: PLC0415

    obs_metrics._get_meter.cache_clear()
    return provider


class TestMetricInstruments:
    """Verify metric instruments are creatable and recordable without errors."""

    def test_orchestrator_request_counter_is_callable(self) -> None:
        """orchestrator_request_counter should return a usable Counter."""
        counter = orchestrator_request_counter()
        counter.add(1, {"agent.mode": "single", "grounded": "true", "tenant.id": "t1"})

    def test_mcp_tool_invocation_counter_is_callable(self) -> None:
        """mcp_tool_invocation_counter should return a usable Counter."""
        counter = mcp_tool_invocation_counter()
        counter.add(1, {"tool.name": "memory_search", "success": "true", "tenant.id": "t1"})

    def test_mcp_tool_error_counter_is_callable(self) -> None:
        """mcp_tool_error_counter should return a usable Counter."""
        counter = mcp_tool_error_counter()
        counter.add(1, {"tool.name": "memory_search", "error.code": "validation_error"})

    def test_pipeline_execution_histogram_is_callable(self) -> None:
        """pipeline_execution_histogram should return a usable Histogram."""
        histogram = pipeline_execution_histogram()
        histogram.record(42.5, {"grounded": "true", "tenant.id": "t1"})

    def test_pipeline_fact_counter_is_callable(self) -> None:
        """pipeline_fact_counter should return a usable Counter."""
        counter = pipeline_fact_counter()
        counter.add(5, {"tenant.id": "t1"})

    def test_configure_metrics_no_op_by_default(self) -> None:
        """configure_metrics with no args should complete without error."""
        provider = configure_metrics()
        assert provider is not None


class TestOrchestratorMetricsEmission:
    """Verify the orchestrator emits request counter after each turn."""

    async def test_respond_emits_request_counter(self) -> None:
        """orchestrator.respond should call orchestrator_request_counter().add(1, ...)."""
        fake_service = AsyncMock()

        async def fake_invoke(request: MCPInvokeRequest) -> MCPInvokeResponse:
            """Return a stub successful response."""
            result = {}
            if request.tool_name == MCPToolName.MEMORY_SEARCH:
                result = {"synthesis": {"response_text": "ok", "grounded": True}}
            return MCPInvokeResponse(
                tool_name=request.tool_name,
                request_id=request.request_id,
                success=True,
                latency_ms=1.0,
                result=result,
                token_usage=MCPTokenUsage(
                    input_tokens=1, output_tokens=1, total_tokens=2, estimated=True
                ),
            )

        fake_service.invoke.side_effect = fake_invoke
        orchestrator = AgentOrchestrator(mcp_tool_service=fake_service)

        mock_counter = MagicMock()
        with patch(
            "src.agent.orchestrator.orchestrator_request_counter",
            return_value=mock_counter,
        ):
            await orchestrator.respond(
                AgentOrchestrationRequest(
                    tenant_id="tenant_metrics",
                    prompt="test prompt",
                    session_id="session_m",
                )
            )

        mock_counter.add.assert_called_once()
        call_args = mock_counter.add.call_args
        assert call_args.args[0] == 1
        attrs = call_args.args[1]
        assert attrs["tenant.id"] == "tenant_metrics"


class TestMCPServiceMetricsEmission:
    """Verify MCP service emits invocation and error counters."""

    @pytest.fixture(autouse=True)
    def _stub_audit_and_counter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub audit persistence and session counter to avoid Spanner calls.

        The audit write is now non-swallowed (Bug A fix); these unit tests must
        stub it so real Spanner calls are not attempted during metrics testing.
        """

        async def fake_record_audit_event(**_: object) -> AuditResponse:
            return AuditResponse(
                tenant_id="tenant_m",
                event_id="audit_stub",
                event_type="MCP_AUTHORIZATION_GRANTED",
                timestamp=datetime.now(UTC),
            )

        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI.record_audit_event",
            fake_record_audit_event,
        )
        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI._increment_session_action_count",
            lambda *_: 1,
        )

    async def test_invoke_success_emits_invocation_counter(self) -> None:
        """Successful invocations should emit to mcp_tool_invocation_counter."""
        fake_pipeline = AsyncMock()
        fake_pipeline.execute.return_value = MagicMock(
            model_dump=lambda mode: {"synthesis": {"response_text": "ok", "grounded": True}}
        )
        service = MCPToolService(mindmap_pipeline=fake_pipeline)

        mock_counter = MagicMock()
        with patch("src.mcp.service.mcp_tool_invocation_counter", return_value=mock_counter):
            await service.invoke(
                MCPInvokeRequest(
                    tenant_id="tenant_m",
                    tool_name=MCPToolName.MEMORY_SEARCH,
                    arguments={"query": "test"},
                )
            )

        mock_counter.add.assert_called_once()
        assert mock_counter.add.call_args.args[0] == 1

    async def test_invoke_failure_emits_error_counter(self) -> None:
        """Failed invocations should emit to mcp_tool_error_counter."""
        service = MCPToolService(mindmap_pipeline=AsyncMock())

        mock_counter = MagicMock()
        with patch("src.mcp.service.mcp_tool_error_counter", return_value=mock_counter):
            await service.invoke(
                MCPInvokeRequest(
                    tenant_id="tenant_m",
                    tool_name=MCPToolName.MEMORY_SEARCH,
                    arguments={"query": "   "},  # blank triggers validation error
                )
            )

        mock_counter.add.assert_called_once()
        assert mock_counter.add.call_args.args[0] == 1


class TestPipelineMetricsEmission:
    """Verify MindMap pipeline emits latency and fact metrics."""

    async def test_execute_emits_histogram_and_fact_counter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pipeline execution should record to histogram and fact counter."""

        async def fake_audit(**_: object) -> AuditResponse:
            """Return stub audit response."""
            return AuditResponse(
                tenant_id="tenant_m",
                event_id="evt_1",
                event_type="MINDMAP_EXECUTION",
                timestamp=datetime.now(UTC),
            )

        monkeypatch.setattr("src.memory.mindmap_pipeline.MemoryAPI.record_audit_event", fake_audit)

        mock_histogram = MagicMock()
        mock_fact_counter = MagicMock()
        with (
            patch(
                "src.memory.mindmap_pipeline.pipeline_execution_histogram",
                return_value=mock_histogram,
            ),
            patch(
                "src.memory.mindmap_pipeline.pipeline_fact_counter",
                return_value=mock_fact_counter,
            ),
        ):
            pipeline = MindMapPipeline()
            await pipeline.execute(query="budget analysis", tenant_id="tenant_m")

        mock_histogram.record.assert_called_once()
        latency_arg = mock_histogram.record.call_args.args[0]
        assert isinstance(latency_arg, float)
        assert latency_arg >= 0.0
        mock_fact_counter.add.assert_called_once()
