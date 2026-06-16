"""Unit tests for Phase 2 MindMap pipeline foundation."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.memory.mindmap_pipeline import (
    AuditTraceRecorder,
    MindMapConfig,
    MindMapPipeline,
    MindMapPipelineError,
    SpannerAggregationAdapter,
)
from src.models.mindmap import (
    MindMapTrace,
    PipelineErrorCode,
    PipelineStage,
    SerializationResult,
    SynthesisResult,
)


class TestMindMapPipeline:
    """Behavioral tests for pipeline orchestration and grounding rules."""

    async def test_execute_rejects_empty_query(self) -> None:
        """Validate empty queries fail fast with stable validation error."""
        pipeline = MindMapPipeline()

        with pytest.raises(MindMapPipelineError, match="query cannot be empty"):
            await pipeline.execute(query="   ")

    async def test_execute_returns_insufficient_when_no_evidence(self) -> None:
        """Ensure synthesis returns explicit insufficiency when no facts exist."""
        pipeline = MindMapPipeline()

        response = await pipeline.execute(query="?")

        assert response.synthesis.response_text == MindMapPipeline.INSUFFICIENT_EVIDENCE_RESPONSE
        assert response.synthesis.claim_fact_ids == []
        assert response.synthesis.grounded is True
        assert response.trace.fact_ids == []

    async def test_execute_links_trace_ids_for_grounded_response(self) -> None:
        """Ensure trace envelope links mined entities, paths, and serialized facts."""
        pipeline = MindMapPipeline()

        response = await pipeline.execute(query="Explain project_alpha budget trend")

        assert response.trace.mined_entities
        assert response.trace.path_ids
        assert response.trace.fact_ids
        assert response.synthesis.claim_fact_ids == response.trace.fact_ids
        assert len(response.trace.stage_timings) == 4

    async def test_pipeline_selects_spanner_adapter_when_enabled(self) -> None:
        """Ensure config flag enables Spanner aggregation adapter."""
        pipeline = MindMapPipeline(config=MindMapConfig(use_spanner_aggregation=True))

        assert isinstance(pipeline.aggregation_adapter, SpannerAggregationAdapter)

    async def test_spanner_aggregation_raises_retrieval_error_when_unavailable(self) -> None:
        """Return stable retrieval error when Spanner client is not initialized."""
        pipeline = MindMapPipeline(config=MindMapConfig(use_spanner_aggregation=True))

        with pytest.raises(MindMapPipelineError, match="spanner retrieval unavailable") as error:
            await pipeline.execute(query="Explain alpha cost")

        assert error.value.stage == PipelineStage.AGGREGATE
        assert error.value.code == PipelineErrorCode.RETRIEVAL_ERROR

    async def test_pipeline_uses_audit_trace_recorder_when_enabled(self) -> None:
        """Enable trace recording should select audit recorder implementation."""
        pipeline = MindMapPipeline(config=MindMapConfig(enable_trace_recording=True))

        assert isinstance(pipeline.trace_recorder, AuditTraceRecorder)

    async def test_pipeline_invokes_custom_trace_recorder(self) -> None:
        """Pipeline should persist generated trace through injected recorder."""

        @dataclass(slots=True)
        class InMemoryTraceRecorder:
            """Simple recorder used to validate recorder invocation in tests."""

            calls: int = 0
            latest_trace_id: str | None = None

            async def record(
                self,
                *,
                trace: MindMapTrace,
                query: str,
                session_id: str | None,
            ) -> None:
                """Capture trace metadata in memory.

                Args:
                    trace: Trace payload from pipeline.
                    query (str): Original query.
                    session_id (str | None): Session identifier.
                """
                del query, session_id
                self.calls += 1
                self.latest_trace_id = trace.trace_id

        recorder = InMemoryTraceRecorder()
        pipeline = MindMapPipeline(trace_recorder=recorder)

        response = await pipeline.execute(query="Explain project alpha trend")

        assert recorder.calls == 1
        assert recorder.latest_trace_id == response.trace.trace_id

    async def test_pipeline_fails_closed_on_ungrounded_claims(self) -> None:
        """Raise grounding error when synthesis references unknown fact IDs."""

        class InvalidSynthesisPipeline(MindMapPipeline):
            """Pipeline variant emitting invalid fact references for testing."""

            def _synthesize(
                self,
                *,
                serialization_result: SerializationResult,
            ) -> SynthesisResult:
                """Emit invalid claim IDs to verify fail-closed grounding behavior.

                Args:
                    serialization_result: Serialized evidence output.

                Returns:
                    SynthesisResult: Invalid synthesized result.
                """
                del serialization_result
                return SynthesisResult(
                    response_text="Invalid grounded response",
                    claim_fact_ids=["fact_does_not_exist"],
                    grounded=True,
                    latency_ms=0.0,
                )

        pipeline = InvalidSynthesisPipeline()

        with pytest.raises(MindMapPipelineError, match="ungrounded claims detected") as error:
            await pipeline.execute(query="Explain project alpha trend")

        assert error.value.stage == PipelineStage.SYNTHESIZE
        assert error.value.code == PipelineErrorCode.GROUNDING_ERROR
