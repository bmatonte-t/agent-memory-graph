"""Integration tests for end-to-end MindMap pipeline flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from src.memory.mindmap_pipeline import (
    DeterministicAggregationAdapter,
    DeterministicMiningAdapter,
    MindMapConfig,
    MindMapPipeline,
)
from src.models.schemas import AuditResponse

if TYPE_CHECKING:
    from src.models.mindmap import MindMapTrace

MAX_MINE_LATENCY_MS = 500.0
MAX_AGGREGATE_LATENCY_MS = 2000.0
MAX_TOTAL_LATENCY_MS = 5000.0
EXPECTED_STAGE_COUNT = 4


@dataclass(slots=True)
class InMemoryTraceRecorder:
    """In-memory recorder used to verify trace persistence wiring in integration tests."""

    calls: int = 0
    last_trace: MindMapTrace | None = None

    async def record(self, *, trace: MindMapTrace, query: str, session_id: str | None) -> None:
        """Capture trace payload and invocation metadata."""
        del query, session_id
        self.calls += 1
        self.last_trace = trace


class TestMindMapIntegration:
    """End-to-end tests for the MindMap pipeline execution path."""

    @pytest.fixture(autouse=True)
    def _stub_audit_trace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub audit persistence to keep integration deterministic and local."""

        async def fake_record_audit_event(**_: object) -> AuditResponse:
            return AuditResponse(
                event_id="audit_test",
                event_type="MINDMAP_EXECUTION",
                timestamp=datetime.now(UTC),
            )

        monkeypatch.setattr(
            "src.memory.mindmap_pipeline.MemoryAPI.record_audit_event",
            fake_record_audit_event,
        )

    async def test_pipeline_end_to_end_returns_traceable_grounded_response(self) -> None:
        """Pipeline should return synthesis + trace linkage for a factual query."""
        recorder = InMemoryTraceRecorder()
        pipeline = MindMapPipeline(trace_recorder=recorder)

        response = await pipeline.execute(query="Explain project alpha budget trend")

        assert response.query == "Explain project alpha budget trend"
        assert response.synthesis.grounded is True
        assert response.trace.mined_entities
        assert response.trace.path_ids
        assert response.trace.fact_ids
        assert response.synthesis.claim_fact_ids == response.trace.fact_ids
        assert recorder.calls == 1
        assert recorder.last_trace is not None
        assert recorder.last_trace.trace_id == response.trace.trace_id

    async def test_pipeline_returns_insufficient_for_no_evidence_query(self) -> None:
        """Insufficient evidence path should be explicit and grounded-safe."""
        pipeline = MindMapPipeline()

        response = await pipeline.execute(query="?")

        assert response.synthesis.response_text == MindMapPipeline.INSUFFICIENT_EVIDENCE_RESPONSE
        assert response.synthesis.claim_fact_ids == []
        assert response.synthesis.grounded is True
        assert response.trace.fact_ids == []

    async def test_pipeline_stage_latency_budget_with_deterministic_adapters(self) -> None:
        """Deterministic adapters should stay under stage and total latency budgets."""
        pipeline = MindMapPipeline(
            config=MindMapConfig(use_spanner_aggregation=False),
            mining_adapter=DeterministicMiningAdapter(),
            aggregation_adapter=DeterministicAggregationAdapter(),
            trace_recorder=InMemoryTraceRecorder(),
        )

        response = await pipeline.execute(query="Explain alpha dependency")

        assert len(response.trace.stage_timings) == EXPECTED_STAGE_COUNT
        timing_by_stage = {
            timing.stage.value: timing.latency_ms for timing in response.trace.stage_timings
        }
        total_latency = sum(timing.latency_ms for timing in response.trace.stage_timings)

        assert timing_by_stage["mine"] < MAX_MINE_LATENCY_MS
        assert timing_by_stage["aggregate"] < MAX_AGGREGATE_LATENCY_MS
        assert total_latency < MAX_TOTAL_LATENCY_MS
