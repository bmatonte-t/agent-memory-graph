"""Unit tests for Phase 2 MindMap pipeline foundation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
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
from src.models.evidence import (
    ContradictionFlag,
    ContradictionSeverity,
    EvidenceContext,
    EvidenceItem,
    EvidenceSourceType,
)
from src.models.mindmap import (
    AggregationResult,
    EvidenceEdge,
    EvidencePath,
    MindMapTrace,
    MinedEntity,
    MiningResult,
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
        assert response.synthesis.claim_fact_ids == response.trace.fact_ids
        if response.trace.path_ids:
            assert response.trace.fact_ids
        else:
            assert (
                response.synthesis.response_text == MindMapPipeline.INSUFFICIENT_EVIDENCE_RESPONSE
            )
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

        with (
            patch(
                "src.memory.mindmap_pipeline.SpannerClient.execute_sql",
                side_effect=RuntimeError("SpannerClient not initialized. Call initialize() first."),
            ),
            pytest.raises(
                MindMapPipelineError,
                match="spanner retrieval unavailable",
            ) as error,
        ):
            await pipeline.execute(query="Explain alpha cost")

        assert error.value.stage == PipelineStage.AGGREGATE
        assert error.value.code == PipelineErrorCode.RETRIEVAL_ERROR

    async def test_spanner_aggregation_uses_graph_query_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Spanner adapter should issue graph-style traversal query with bounded hops."""
        captured_sql: str | None = None
        captured_params: dict[str, object] | None = None

        def fake_execute_sql(sql: str, params: dict[str, object]) -> list[tuple[str, ...]]:
            nonlocal captured_sql, captured_params
            captured_sql = sql
            captured_params = params
            return []

        monkeypatch.setattr(
            "src.memory.mindmap_pipeline.SpannerClient.execute_sql",
            fake_execute_sql,
        )
        pipeline = MindMapPipeline(config=MindMapConfig(use_spanner_aggregation=True, max_hops=4))

        await pipeline.execute(query="Explain alpha dependency")

        assert captured_sql is not None
        assert captured_params is not None
        sql = captured_sql
        params = captured_params
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
                authorization_scope: object | None = None,
            ) -> None:
                """Capture trace metadata in memory.

                Args:
                    trace: Trace payload from pipeline.
                    query (str): Original query.
                    session_id (str | None): Session identifier.
                    tenant_id (str | None): Tenant identifier.
                    authorization_scope (object | None): Optional auth scope.
                """
                del query, session_id, tenant_id, authorization_scope
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
                mining_result: object,
                tenant_id: str | None = None,
                evidence_context: object | None = None,
            ) -> SynthesisResult:
                """Emit invalid claim IDs to verify fail-closed grounding behavior.

                Args:
                    serialization_result: Serialized evidence output.
                    mining_result: Mined entities (unused).
                    tenant_id: Tenant ID (unused).
                    evidence_context: Evidence context (unused).

                Returns:
                    SynthesisResult: Invalid synthesized result.
                """
                del serialization_result, mining_result, tenant_id, evidence_context
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

        mining_result = MiningResult(
            intent="information_lookup",
            entities=[],
            latency_ms=0.0,
        )

        with (
            patch("builtins.__import__", side_effect=ImportError("No module")),
            pytest.raises(
                MindMapPipelineError,
                match="google-generativeai is required for vertex synthesis",
            ) as error,
        ):
            pipeline._synthesize_with_vertex(
                serialization_result=serialization_result,
                mining_result=mining_result,
            )

        assert error.value.stage == PipelineStage.SYNTHESIZE
        assert error.value.code == PipelineErrorCode.MODEL_ERROR

    async def test_vertex_synthesis_returns_insufficient_for_empty_facts(self) -> None:
        """Vertex synthesis path should fail closed when serialization has no facts."""
        pipeline = MindMapPipeline(config=MindMapConfig(use_vertex_synthesis=True))
        serialization_result = SerializationResult(facts=[], markdown="", latency_ms=0.0)

        mining_result = MiningResult(
            intent="information_lookup",
            entities=[],
            latency_ms=0.0,
        )

        result = pipeline._synthesize_with_vertex(
            serialization_result=serialization_result,
            mining_result=mining_result,
        )

        assert result.response_text == MindMapPipeline.INSUFFICIENT_EVIDENCE_RESPONSE
        assert result.claim_fact_ids == []
        assert result.grounded is True

    async def test_synthesize_soft_signals_low_confidence_and_contradictions(self) -> None:
        """Soft gating should keep the response but annotate low-confidence evidence."""
        pipeline = MindMapPipeline(
            config=MindMapConfig(
                confidence_threshold=0.3,
                synthesis_gating_mode="soft_signal",
                enable_contradiction_detection=True,
            )
        )
        serialization_result = SerializationResult(
            facts=[
                SerializedFact(
                    fact_id="fact_1",
                    statement="FACT 1: (patient) -[has_symptom:0.80]-> (fever)",
                    path_id="path_1",
                    edge_ids=["edge_1"],
                    rel_type="has_symptom",
                    weight=0.80,
                )
            ],
            markdown="FACT 1: (patient) -[has_symptom:0.80]-> (fever)",
            latency_ms=0.0,
        )
        mining_result = MiningResult(
            intent="information_lookup",
            entities=[MinedEntity(entity_id="patient", entity_type="OBJECT", confidence=0.90)],
            latency_ms=0.0,
        )
        evidence_context = EvidenceContext(
            items=[
                EvidenceItem(
                    evidence_id="evid_1",
                    source_type=EvidenceSourceType.PATH_BASED,
                    evidence_number=1,
                    graph_path="patient->has_symptom->fever",
                    serialized_form="patient->has_symptom->fever",
                    access_timestamp=datetime.now(UTC),
                    source_confidence_score=0.1,
                    contradiction_flags=["high:node_1"],
                )
            ],
            total_items=1,
            path_count=1,
            neighbor_count=0,
            is_empty=False,
            is_sufficient=True,
            retrieval_latency_ms=1.0,
        )

        result = pipeline._synthesize(
            serialization_result=serialization_result,
            mining_result=mining_result,
            tenant_id="tenant-123",
            evidence_context=evidence_context,
        )

        assert result.response_text.startswith("Grounded summary:")
        assert "Phase 5 confidence signal" in result.response_text
        assert result.confidence_signal is not None
        assert result.confidence_signal.gating_applied == "soft_signal"
        assert result.confidence_score == result.confidence_signal.response_confidence_score
        assert result.contradiction_warnings

    async def test_synthesize_hard_rejects_low_confidence_evidence(self) -> None:
        """Hard gating should return explicit insufficiency for low-confidence evidence."""
        pipeline = MindMapPipeline(
            config=MindMapConfig(
                confidence_threshold=0.3,
                synthesis_gating_mode="hard_reject",
                enable_contradiction_detection=True,
            )
        )
        serialization_result = SerializationResult(
            facts=[
                SerializedFact(
                    fact_id="fact_1",
                    statement="FACT 1: (patient) -[has_symptom:0.80]-> (fever)",
                    path_id="path_1",
                    edge_ids=["edge_1"],
                    rel_type="has_symptom",
                    weight=0.80,
                )
            ],
            markdown="FACT 1: (patient) -[has_symptom:0.80]-> (fever)",
            latency_ms=0.0,
        )
        mining_result = MiningResult(
            intent="information_lookup",
            entities=[MinedEntity(entity_id="patient", entity_type="OBJECT", confidence=0.90)],
            latency_ms=0.0,
        )
        evidence_context = EvidenceContext(
            items=[
                EvidenceItem(
                    evidence_id="evid_1",
                    source_type=EvidenceSourceType.PATH_BASED,
                    evidence_number=1,
                    graph_path="patient->has_symptom->fever",
                    serialized_form="patient->has_symptom->fever",
                    access_timestamp=datetime.now(UTC),
                    source_confidence_score=0.1,
                    contradiction_flags=["high:node_1"],
                )
            ],
            total_items=1,
            path_count=1,
            neighbor_count=0,
            is_empty=False,
            is_sufficient=True,
            retrieval_latency_ms=1.0,
        )

        result = pipeline._synthesize(
            serialization_result=serialization_result,
            mining_result=mining_result,
            tenant_id="tenant-123",
            evidence_context=evidence_context,
        )

        assert result.response_text == MindMapPipeline.INSUFFICIENT_EVIDENCE_RESPONSE
        assert result.claim_fact_ids == []
        assert result.confidence_signal is not None
        assert result.confidence_signal.gating_applied == "hard_reject"

    async def test_spanner_aggregation_adapter_rejects_none_node_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Row with None node_id must raise ValueError, not silently produce 'None' string.

        The SpannerAggregationAdapter row-processing loop must validate that
        source_node_id is not None before calling str() on it. Silently producing
        the string 'None' would corrupt the graph node dictionary.

        Note on test approach: the review suggested calling _build_evidence_nodes directly
        on a SpannerAggregationAdapter instance. However, that method does not exist as a
        standalone method — the None-guard logic is inline inside aggregate(). Direct
        instantiation of SpannerAggregationAdapter is straightforward (no __init__ args),
        but calling aggregate() directly requires constructing MiningResult/MindMapConfig
        stubs and still patches SpannerClient. Invoking via MindMapPipeline.execute() with
        a monkeypatched SpannerClient is equivalent depth and avoids duplicating the
        aggregate() call-site setup. The full-pipeline approach is kept intentionally.
        """
        rows_with_none: list[tuple[object, ...]] = [
            (None, "SEMANTIC", "person", 1.0, "edge_1", "dest_node", "KNOWS", 0.5),
        ]
        monkeypatch.setattr(
            "src.memory.mindmap_pipeline.SpannerClient.execute_sql",
            lambda *_args, **_kwargs: rows_with_none,
        )
        pipeline = MindMapPipeline(config=MindMapConfig(use_spanner_aggregation=True))

        with pytest.raises(ValueError, match="node_id cannot be None"):
            await pipeline.execute(query="Explain alpha dependency")

    async def test_spanner_aggregation_adapter_rejects_none_destination_node_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Row with None destination_node_id must raise ValueError, not silently produce 'None'.

        The SpannerAggregationAdapter row-processing loop must validate that
        destination_node_id is not None before calling str() on it. Silently producing
        the string 'None' would corrupt the edge and path data, creating phantom nodes
        in the evidence graph. The guard is symmetric with the source_node_id guard
        already in place (Bug B fix).
        """
        rows_with_none_dest: list[tuple[object, ...]] = [
            ("source_node", "SEMANTIC", "person", 1.0, "edge_1", None, "KNOWS", 0.5),
        ]
        monkeypatch.setattr(
            "src.memory.mindmap_pipeline.SpannerClient.execute_sql",
            lambda *_args, **_kwargs: rows_with_none_dest,
        )
        pipeline = MindMapPipeline(config=MindMapConfig(use_spanner_aggregation=True))

        with pytest.raises(ValueError, match="destination_node_id cannot be None"):
            await pipeline.execute(query="Explain alpha dependency")

    async def test_vertex_synthesis_hard_rejects_low_confidence_evidence(self) -> None:
        """Vertex synthesis should short-circuit before model invocation when hard gated."""
        pipeline = MindMapPipeline(
            config=MindMapConfig(
                use_vertex_synthesis=True,
                confidence_threshold=0.3,
                synthesis_gating_mode="hard_reject",
                enable_contradiction_detection=True,
            )
        )
        serialization_result = SerializationResult(
            facts=[
                SerializedFact(
                    fact_id="fact_1",
                    statement="FACT 1: (patient) -[has_symptom:0.80]-> (fever)",
                    path_id="path_1",
                    edge_ids=["edge_1"],
                    rel_type="has_symptom",
                    weight=0.80,
                )
            ],
            markdown="FACT 1: (patient) -[has_symptom:0.80]-> (fever)",
            latency_ms=0.0,
        )
        mining_result = MiningResult(
            intent="information_lookup",
            entities=[MinedEntity(entity_id="patient", entity_type="OBJECT", confidence=0.90)],
            latency_ms=0.0,
        )
        evidence_context = EvidenceContext(
            items=[
                EvidenceItem(
                    evidence_id="evid_1",
                    source_type=EvidenceSourceType.PATH_BASED,
                    evidence_number=1,
                    graph_path="patient->has_symptom->fever",
                    serialized_form="patient->has_symptom->fever",
                    access_timestamp=datetime.now(UTC),
                    source_confidence_score=0.1,
                    contradiction_flags=["high:node_1"],
                )
            ],
            total_items=1,
            path_count=1,
            neighbor_count=0,
            is_empty=False,
            is_sufficient=True,
            retrieval_latency_ms=1.0,
        )

        result = pipeline._synthesize_with_vertex(
            serialization_result=serialization_result,
            mining_result=mining_result,
            tenant_id="tenant-123",
            evidence_context=evidence_context,
        )

        assert result.response_text == MindMapPipeline.INSUFFICIENT_EVIDENCE_RESPONSE
        assert result.claim_fact_ids == []
        assert result.confidence_signal is not None
        assert result.confidence_signal.gating_applied == "hard_reject"


class TestContradictionFlag:
    """Tests for the ContradictionFlag dataclass and parsing."""

    def test_contradiction_flag_from_string_valid(self) -> None:
        """Standard format parses correctly into severity and node_id."""
        flag = ContradictionFlag.from_string("HIGH:node-123")
        assert flag.severity == ContradictionSeverity.HIGH
        assert flag.node_id == "node-123"

    def test_contradiction_flag_from_string_node_id_with_colon(self) -> None:
        """node_id containing ':' is captured fully in second split part."""
        flag = ContradictionFlag.from_string("LOW:node:with:colons")
        assert flag.severity == ContradictionSeverity.LOW
        assert flag.node_id == "node:with:colons"

    def test_contradiction_flag_from_string_invalid_severity(self) -> None:
        """Invalid severity raises ValueError with a descriptive message."""
        with pytest.raises(ValueError, match="CRITICAL"):
            ContradictionFlag.from_string("CRITICAL:node-123")

    def test_contradiction_flag_from_string_missing_separator(self) -> None:
        """Missing ':' separator raises ValueError."""
        with pytest.raises(ValueError, match="Invalid contradiction flag format"):
            ContradictionFlag.from_string("HIGH-node-123")

    def test_contradiction_flag_from_string_empty_node_id(self) -> None:
        """Empty node_id after ':' raises ValueError."""
        with pytest.raises(ValueError, match="node_id cannot be empty"):
            ContradictionFlag.from_string("HIGH:")

    def test_contradiction_flag_case_insensitive_severity(self) -> None:
        """Severity is uppercased before enum lookup, so lowercase input also works."""
        flag = ContradictionFlag.from_string("medium:node-456")
        assert flag.severity == ContradictionSeverity.MEDIUM
        assert flag.node_id == "node-456"

    def test_contradiction_flag_is_frozen(self) -> None:
        """ContradictionFlag is immutable (frozen dataclass)."""
        flag = ContradictionFlag.from_string("LOW:node-789")
        with pytest.raises(FrozenInstanceError):
            flag.node_id = "other"  # type: ignore[misc]
