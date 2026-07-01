"""Integration tests for Cloud Trace span export across the agent pipeline.

Validates that spans are emitted with correct names and attributes through the
orchestrator, MCP service, and MindMap pipeline execution paths.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from src.agent.orchestrator import AgentOrchestrator
from src.mcp.service import MCPToolService
from src.memory.mindmap_pipeline import MindMapPipeline
from src.models.agent import AgentOrchestrationRequest
from src.models.mcp import MCPInvokeRequest, MCPInvokeResponse, MCPTokenUsage, MCPToolName
from src.models.schemas import AuditResponse
from src.observability.tracing import configure_tracer, trace_span


@pytest.fixture(scope="module")
def span_exporter() -> InMemorySpanExporter:
    """Provide a shared in-memory span exporter for the test module.

    Returns:
        InMemorySpanExporter: Exporter configured once for the module.
    """
    exporter = InMemorySpanExporter()
    configure_tracer(span_exporter=exporter, _allow_reset=True)
    return exporter


@pytest.fixture(autouse=True)
def _clear_spans(span_exporter: InMemorySpanExporter) -> None:
    """Clear captured spans before each test for isolation.

    Args:
        span_exporter: Module-level span exporter fixture.
    """
    span_exporter.clear()


class TestTraceSpanHelper:
    """Unit-level tests for the trace_span context manager."""

    def test_span_records_attributes(self, span_exporter: InMemorySpanExporter) -> None:
        """Span attributes should be accessible after the context manager exits."""
        with trace_span("test.span", attributes={"tenant.id": "t1", "session.id": "s1"}):
            pass

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test.span"
        assert spans[0].attributes["tenant.id"] == "t1"
        assert spans[0].attributes["session.id"] == "s1"

    def test_span_records_exception_and_error_status(
        self, span_exporter: InMemorySpanExporter
    ) -> None:
        """Exceptions inside the span body should be recorded with ERROR status."""
        error_message = "test error"

        with pytest.raises(ValueError, match=error_message), trace_span("test.error_span"):
            raise ValueError(error_message)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.ERROR
        assert spans[0].events, "exception event should be recorded"

    def test_nested_spans_create_parent_child_relationship(
        self, span_exporter: InMemorySpanExporter
    ) -> None:
        """Inner spans should be children of the outer span."""
        with trace_span("parent.span"), trace_span("child.span"):
            pass

        spans = span_exporter.get_finished_spans()
        expected_span_count = 2
        assert len(spans) == expected_span_count
        span_names = {s.name for s in spans}
        assert "parent.span" in span_names
        assert "child.span" in span_names

        child = next(s for s in spans if s.name == "child.span")
        parent = next(s for s in spans if s.name == "parent.span")
        assert child.parent is not None
        assert child.parent.span_id == parent.context.span_id


class TestOrchestratorTracing:
    """Verify span emission from the agent orchestrator."""

    async def test_respond_emits_orchestrator_span(
        self, span_exporter: InMemorySpanExporter
    ) -> None:
        """orchestrator.respond span should carry tenant, session, and mode attributes."""
        fake_service = AsyncMock()

        async def fake_invoke(request: MCPInvokeRequest) -> MCPInvokeResponse:
            """Return a stub successful tool response."""
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

        await orchestrator.respond(
            AgentOrchestrationRequest(
                tenant_id="tenant_trace",
                prompt="what is the budget?",
                session_id="session_trace",
                request_id="req_trace",
            )
        )

        finished_spans = span_exporter.get_finished_spans()
        span_names = [s.name for s in finished_spans]
        assert "orchestrator.respond" in span_names

        orch_span = next(s for s in finished_spans if s.name == "orchestrator.respond")
        assert orch_span.attributes["tenant.id"] == "tenant_trace"
        assert orch_span.attributes["session.id"] == "session_trace"
        assert orch_span.attributes["request.id"] == "req_trace"


class TestMCPServiceTracing:
    """Verify span emission from the MCP tool service."""

    async def test_invoke_emits_mcp_span(
        self,
        span_exporter: InMemorySpanExporter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """mcp.invoke span should carry tool name, tenant, session, and request context."""
        fake_pipeline = AsyncMock()
        fake_pipeline.execute.return_value = MagicMock(
            model_dump=lambda mode: {
                "synthesis": {"response_text": "ok", "grounded": True},
            }
        )
        service = MCPToolService(mindmap_pipeline=fake_pipeline)

        # Stub audit event write — now propagates (Bug A fix), must be stubbed in unit tests.
        async def fake_record_audit_event(**_: object) -> AuditResponse:
            return AuditResponse(
                tenant_id="tenant_mcp",
                event_id="audit_stub",
                event_type="MCP_AUTHORIZATION_GRANTED",
                timestamp=datetime.now(UTC),
            )

        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI.record_audit_event",
            fake_record_audit_event,
        )

        # Mock the session action counter to avoid SpannerClient initialization
        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI._increment_session_action_count",
            lambda *_: None,
        )

        await service.invoke(
            MCPInvokeRequest(
                tenant_id="tenant_mcp",
                tool_name=MCPToolName.MEMORY_SEARCH,
                arguments={"query": "test query"},
                session_id="session_mcp",
                request_id="req_mcp",
            )
        )

        finished_spans = span_exporter.get_finished_spans()
        span_names = [s.name for s in finished_spans]
        assert "mcp.invoke" in span_names

        mcp_span = next(s for s in finished_spans if s.name == "mcp.invoke")
        assert mcp_span.attributes["tool.name"] == "memory_search"
        assert mcp_span.attributes["tenant.id"] == "tenant_mcp"
        assert mcp_span.attributes["session.id"] == "session_mcp"
        assert mcp_span.attributes["request.id"] == "req_mcp"


class TestMindMapPipelineTracing:
    """Verify span emission from the MindMap pipeline."""

    async def test_execute_emits_mindmap_span(
        self,
        span_exporter: InMemorySpanExporter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """mindmap.execute span should carry session, tenant, and query length attributes."""

        async def fake_audit(**_: object) -> AuditResponse:
            """Return a stub audit response."""
            return AuditResponse(
                tenant_id="tenant_mm",
                event_id="evt_1",
                event_type="MINDMAP_EXECUTION",
                timestamp=datetime.now(UTC),
            )

        monkeypatch.setattr(
            "src.memory.mindmap_pipeline.MemoryAPI.record_audit_event",
            fake_audit,
        )

        pipeline = MindMapPipeline()
        await pipeline.execute(
            query="Explain alpha budget",
            session_id="session_mm",
            tenant_id="tenant_mm",
        )

        finished_spans = span_exporter.get_finished_spans()
        span_names = [s.name for s in finished_spans]
        assert "mindmap.execute" in span_names

        mm_span = next(s for s in finished_spans if s.name == "mindmap.execute")
        assert mm_span.attributes["session.id"] == "session_mm"
        assert mm_span.attributes["tenant.id"] == "tenant_mm"
        assert isinstance(mm_span.attributes["query.length"], int)
        assert mm_span.attributes["query.length"] > 0
