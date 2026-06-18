"""Unit tests for Phase 2 MindMap pipeline foundation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.memory.mindmap_pipeline import (
    AuditTraceRecorder,
    MindMapConfig,
    MindMapPipeline,
    MindMapPipelineError,
    SpannerAggregationAdapter,
    VertexMiningAdapter,
)
from src.models.mindmap import (
    AggregationResult,
    EvidenceEdge,
    EvidencePath,
    MindMapTrace,
    PipelineErrorCode,
    PipelineStage,
    SerializationResult,
    SerializedFact,
    SynthesisResult,
)
from src.models.schemas import AuditResponse

EXPECTED_STAGE_COUNT = 4


class TestMindMapPipeline:
    """Behavioral tests for pipeline orchestration and grounding rules."""

    @pytest.fixture(autouse=True)
    def _stub_audit_trace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub audit persistence for tests that execute pipeline with default config."""

        async def fake_record_audit_event(**_: object) -> AuditResponse:
            return AuditResponse(
                tenant_id="tenant_mindmap",
                event_id="audit_test",
                event_type="MINDMAP_EXECUTION",
                timestamp=datetime.now(UTC),
            )

        monkeypatch.setattr(
            "src.memory.mindmap_pipeline.MemoryAPI.record_audit_event",
            fake_record_audit_event,
        )

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
        assert len(response.trace.stage_timings) == EXPECTED_STAGE_COUNT

    async def test_pipeline_selects_spanner_adapter_when_enabled(self) -> None:
        """Ensure config flag enables Spanner aggregation adapter."""
        pipeline = MindMapPipeline(config=MindMapConfig(use_spanner_aggregation=True))

        assert isinstance(pipeline.aggregation_adapter, SpannerAggregationAdapter)

    async def test_pipeline_selects_vertex_mining_adapter_when_enabled(self) -> None:
        """Ensure config flag enables Vertex mining adapter selection."""
        pipeline = MindMapPipeline(config=MindMapConfig(use_vertex_mining=True))

        assert isinstance(pipeline.mining_adapter, VertexMiningAdapter)

    async def test_spanner_aggregation_raises_retrieval_error_when_unavailable(self) -> None:
        """Return stable retrieval error when Spanner client is not initialized."""
        pipeline = MindMapPipeline(config=MindMapConfig(use_spanner_aggregation=True))

        with pytest.raises(MindMapPipelineError, match="spanner retrieval unavailable") as error:
            await pipeline.execute(query="Explain alpha cost")

        assert error.value.stage == PipelineStage.AGGREGATE
        assert error.value.code == PipelineErrorCode.RETRIEVAL_ERROR

    async def test_spanner_aggregation_uses_graph_query_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Spanner adapter should issue graph-style traversal query with bounded hops."""
        captured: dict[str, object] = {}

        def fake_execute_sql(sql: str, params: dict[str, object]) -> list[tuple[str, ...]]:
            captured["sql"] = sql
            captured["params"] = params
            return []

        monkeypatch.setattr(
            "src.memory.mindmap_pipeline.SpannerClient.execute_sql",
            fake_execute_sql,
        )
        pipeline = MindMapPipeline(config=MindMapConfig(use_spanner_aggregation=True, max_hops=4))

        await pipeline.execute(query="Explain alpha dependency")

        sql = str(captured["sql"])
        params = dict(captured["params"])
        assert "GRAPH MemoryGraph" in sql
        assert "MemoryEdge*1..4" in sql
        assert "m.MemoryTier IN ('SEMANTIC', 'CONTEXT')" in sql
        assert params["threshold"] == pipeline.config.cognitive_weight_threshold

    async def test_pipeline_uses_audit_trace_recorder_when_enabled(self) -> None:
        """Enable trace recording should select audit recorder implementation."""
        pipeline = MindMapPipeline(config=MindMapConfig(enable_trace_recording=True))

        assert isinstance(pipeline.trace_recorder, AuditTraceRecorder)

    async def test_pipeline_defaults_to_audit_trace_recorder(self) -> None:
        """Default configuration should persist trace metadata via audit recorder."""
        pipeline = MindMapPipeline()

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
                tenant_id: str | None,
            ) -> None:
                """Capture trace metadata in memory.

                Args:
                    trace: Trace payload from pipeline.
                    query (str): Original query.
                    session_id (str | None): Session identifier.
                    tenant_id (str | None): Tenant identifier.
                """
                del query, session_id, tenant_id
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

    async def test_serialize_includes_edge_rel_type_and_weight(self) -> None:
        """Serialized facts should include relationship type and edge weight provenance."""
        pipeline = MindMapPipeline()
        aggregation_result = AggregationResult(
            nodes=[],
            edges=[
                EvidenceEdge(
                    edge_id="edge_1",
                    source_node_id="node_a",
                    destination_node_id="node_b",
                    rel_type="DEPENDS_ON",
                    weight=0.73,
                )
            ],
            paths=[
                EvidencePath(
                    path_id="path_1",
                    node_ids=["node_a", "node_b"],
                    edge_ids=["edge_1"],
                )
            ],
            latency_ms=0.0,
        )

        result = pipeline._serialize(aggregation_result=aggregation_result)

        assert result.facts
        fact = result.facts[0]
        assert fact.rel_type == "DEPENDS_ON"
        assert fact.weight == pytest.approx(0.73, abs=0.001)
        assert "DEPENDS_ON:0.73" in fact.statement

    async def test_vertex_synthesis_raises_model_error_when_dependency_missing(self) -> None:
        """Vertex synthesis should return a stable model error when SDK is unavailable."""
        pipeline = MindMapPipeline(config=MindMapConfig(use_vertex_synthesis=True))
        serialization_result = SerializationResult(
            facts=[
                SerializedFact(
                    fact_id="fact_1",
                    statement="FACT 1: (a) -[RELATED_TO:0.50]-> (b)",
                    path_id="path_1",
                    edge_ids=["edge_1"],
                    rel_type="RELATED_TO",
                    weight=0.5,
                )
            ],
            markdown="FACT 1: (a) -[RELATED_TO:0.50]-> (b)",
            latency_ms=0.0,
        )

        with (
            patch("builtins.__import__", side_effect=ImportError("No module")),
            pytest.raises(
                MindMapPipelineError,
                match="google-generativeai is required for vertex synthesis",
            ) as error,
        ):
            pipeline._synthesize_with_vertex(serialization_result=serialization_result)

        assert error.value.stage == PipelineStage.SYNTHESIZE
        assert error.value.code == PipelineErrorCode.MODEL_ERROR

    async def test_vertex_synthesis_returns_insufficient_for_empty_facts(self) -> None:
        """Vertex synthesis path should fail closed when serialization has no facts."""
        pipeline = MindMapPipeline(config=MindMapConfig(use_vertex_synthesis=True))
        serialization_result = SerializationResult(facts=[], markdown="", latency_ms=0.0)

        result = pipeline._synthesize_with_vertex(serialization_result=serialization_result)

        assert result.response_text == MindMapPipeline.INSUFFICIENT_EVIDENCE_RESPONSE
        assert result.claim_fact_ids == []
        assert result.grounded is True
