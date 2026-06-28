"""Integration tests for Phase 4E: LLM synthesis with evidence integration.

Tests:
- Evidence context building from mined entities
- Evidence annotation in synthesis prompts
- Sufficiency signals in MindMapResponse
- Evidence summary generation
- Determinism of evidence serialization
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.memory.evidence_service import EvidenceService
from src.memory.mindmap_pipeline import MindMapConfig, MindMapPipeline
from src.models.evidence import (
    EvidenceContext,
    EvidenceInsufficientReason,
    EvidenceItem,
    EvidenceSourceType,
    EvidenceSummary,
)
from src.models.mindmap import (
    MinedEntity,
    MiningResult,
    SerializationResult,
    SerializedFact,
)

EVIDENCE_SUMMARY_TOTAL_ITEMS = 2
EVIDENCE_SUMMARY_PATH_COUNT = 1
EVIDENCE_SUMMARY_NEIGHBOR_COUNT = 1
EVIDENCE_SUMMARY_LATENCY_MS = 35.0


class TestEvidenceServiceBuildContext:
    """Test EvidenceService.build_evidence_context() orchestration."""

    @pytest.mark.asyncio
    async def test_build_evidence_context_with_valid_entities(self) -> None:
        """Valid entities should produce evidence context."""
        # Arrange
        mock_client = Mock()
        service = EvidenceService(mock_client)

        # Mock PathFinder and NeighborEnricher at the method import location
        with (
            patch("src.memory.retrieval.EvidentPathFinder") as mock_path_finder_class,
            patch("src.memory.retrieval.NeighborEnricher") as mock_enricher_class,
        ):
            mock_finder = AsyncMock()
            mock_finder.find_paths = AsyncMock(
                return_value=(
                    ["patient->has_symptom->fever", "patient->indicates->infection"],
                    45,
                )
            )
            mock_path_finder_class.return_value = mock_finder

            mock_enricher = AsyncMock()
            mock_enricher.enrich_neighbors = AsyncMock(
                return_value=(
                    ["patient->has_symptom->cough,fever", "patient->indicates->diagnosis"],
                    40,
                )
            )
            mock_enricher_class.return_value = mock_enricher

            # Act
            result = await service.build_evidence_context(
                tenant_id="tenant-123",
                mined_entities=["patient", "fever"],
                session_id="sess-456",
            )

        # Assert
        assert result is not None
        assert result.total_items > 0
        assert result.path_count > 0
        assert result.neighbor_count > 0
        assert result.total_chars > 0

    @pytest.mark.asyncio
    async def test_build_evidence_context_empty_entities(self) -> None:
        """Empty entity list should return empty context."""
        # Arrange
        mock_client = Mock()
        service = EvidenceService(mock_client)

        # Act
        result = await service.build_evidence_context(
            tenant_id="tenant-123",
            mined_entities=[],
            session_id="sess-456",
        )

        # Assert
        assert result.is_empty is True
        assert result.total_items == 0
        assert result.insufficient_reasons == [EvidenceInsufficientReason.EMPTY_GRAPH]

    @pytest.mark.asyncio
    async def test_build_evidence_context_invalid_tenant_id(self) -> None:
        """Empty tenant_id should raise ValueError."""
        # Arrange
        mock_client = Mock()
        service = EvidenceService(mock_client)

        # Act & Assert
        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            await service.build_evidence_context(
                tenant_id="",
                mined_entities=["patient"],
            )

    @pytest.mark.asyncio
    async def test_build_evidence_context_error_handling(self) -> None:
        """Errors during retrieval should return context with insufficient reasons."""
        # Arrange
        mock_client = Mock()
        service = EvidenceService(mock_client)

        # Mock PathFinder to raise error
        with patch("src.memory.retrieval.EvidentPathFinder") as mock_path_finder_class:
            mock_finder = AsyncMock()
            mock_finder.find_paths = AsyncMock(side_effect=RuntimeError("Timeout"))
            mock_path_finder_class.return_value = mock_finder

            # Act
            result = await service.build_evidence_context(
                tenant_id="tenant-123",
                mined_entities=["patient", "provider"],
            )

        # Assert
        assert result is not None
        assert EvidenceInsufficientReason.UNKNOWN in result.insufficient_reasons


class TestMindMapPipelineEvidenceIntegration:
    """Test MindMapPipeline integration with evidence service."""

    @pytest.mark.asyncio
    async def test_execute_includes_evidence_summary(self) -> None:
        """MindMapResponse should include evidence_summary when tenant_id provided."""
        # Arrange
        config = MindMapConfig(use_vertex_synthesis=False, enable_trace_recording=False)
        mock_spanner_client = Mock()
        pipeline = MindMapPipeline(config=config, spanner_client=mock_spanner_client)

        # Mock evidence service
        now = datetime.now(UTC)
        mock_evidence_context = EvidenceContext(
            items=[
                EvidenceItem(
                    evidence_id="evid_1",
                    source_type=EvidenceSourceType.PATH_BASED,
                    evidence_number=1,
                    graph_path="patient->has_symptom->fever",
                    serialized_form="patient->has_symptom->fever",
                    access_timestamp=now,
                    cognitive_weight=1.0,
                ),
            ],
            total_items=1,
            total_chars=30,
            path_count=1,
            neighbor_count=0,
            is_empty=False,
            is_sufficient=False,
            insufficient_reasons=[EvidenceInsufficientReason.NO_NEIGHBORS_FOUND],
            retrieval_latency_ms=50.0,
        )

        with patch.object(
            pipeline.evidence_service,
            "build_evidence_context",
            new_callable=AsyncMock,
        ) as mock_build_evidence:
            mock_build_evidence.return_value = mock_evidence_context

            # Act
            response = await pipeline.execute(
                query="What is the patient's condition?",
                tenant_id="tenant-123",
                session_id="sess-456",
            )

        # Assert
        assert response.evidence_summary is not None
        assert response.evidence_summary.total_items == 1
        assert response.evidence_summary.path_count == 1
        assert response.evidence_summary.neighbor_count == 0
        assert response.evidence_summary.is_sufficient is False
        assert (
            EvidenceInsufficientReason.NO_NEIGHBORS_FOUND
            in response.evidence_summary.insufficient_reasons
        )

    @pytest.mark.asyncio
    async def test_execute_without_tenant_id_skips_evidence(self) -> None:
        """Without tenant_id, evidence service should not be called."""
        # Arrange
        config = MindMapConfig(use_vertex_synthesis=False, enable_trace_recording=False)
        mock_spanner_client = Mock()
        pipeline = MindMapPipeline(config=config, spanner_client=mock_spanner_client)

        with patch.object(
            pipeline.evidence_service,
            "build_evidence_context",
            new_callable=AsyncMock,
        ) as mock_build_evidence:
            # Act
            response = await pipeline.execute(
                query="What is the patient's condition?",
                tenant_id=None,
                session_id="sess-456",
            )

        # Assert
        assert response.evidence_summary is None
        mock_build_evidence.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_evidence_error_handling(self) -> None:
        """Evidence service errors should not break pipeline execution."""
        # Arrange
        config = MindMapConfig(use_vertex_synthesis=False, enable_trace_recording=False)
        mock_spanner_client = Mock()
        pipeline = MindMapPipeline(config=config, spanner_client=mock_spanner_client)

        with patch.object(
            pipeline.evidence_service,
            "build_evidence_context",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Evidence retrieval failed"),
        ):
            # Act - should not raise
            response = await pipeline.execute(
                query="What is the patient's condition?",
                tenant_id="tenant-123",
                session_id="sess-456",
            )

        # Assert
        assert response is not None
        assert response.synthesis is not None


class TestSynthesisEvidenceAnnotation:
    """Test evidence annotation in synthesis methods."""

    def test_synthesize_annotates_insufficient_evidence(self) -> None:
        """_synthesize should annotate insufficient evidence in response."""
        # Arrange
        config = MindMapConfig()
        mock_spanner_client = Mock()
        pipeline = MindMapPipeline(config=config, spanner_client=mock_spanner_client)

        serialization_result = SerializationResult(
            facts=[
                SerializedFact(
                    fact_id="fact_1",
                    statement="FACT 1: (patient) -[has_symptom:0.80]-> (fever)",
                    path_id="path_1",
                    edge_ids=["edge_1"],
                    rel_type="has_symptom",
                    weight=0.80,
                ),
            ],
            markdown="FACT 1: (patient) -[has_symptom:0.80]-> (fever)",
            latency_ms=10.0,
        )

        mining_result = MiningResult(
            intent="information_lookup",
            entities=[MinedEntity(entity_id="patient", entity_type="OBJECT", confidence=0.90)],
            latency_ms=5.0,
        )

        # Create mock evidence context with insufficient signals
        mock_evidence_context = EvidenceContext(
            items=[],
            total_items=0,
            total_chars=0,
            path_count=0,
            neighbor_count=0,
            is_empty=True,
            is_sufficient=False,
            insufficient_reasons=[
                EvidenceInsufficientReason.NO_PATHS_FOUND,
                EvidenceInsufficientReason.NO_NEIGHBORS_FOUND,
            ],
            retrieval_latency_ms=25.0,
        )

        # Act
        result = pipeline._synthesize(
            serialization_result=serialization_result,
            mining_result=mining_result,
            tenant_id="tenant-123",
            evidence_context=mock_evidence_context,
        )

        # Assert
        assert "⚠️  Evidence insufficiency" in result.response_text
        assert result.response_text is not None

    def test_synthesize_without_evidence_context(self) -> None:
        """_synthesize without evidence context should work normally."""
        # Arrange
        config = MindMapConfig()
        mock_spanner_client = Mock()
        pipeline = MindMapPipeline(config=config, spanner_client=mock_spanner_client)

        serialization_result = SerializationResult(
            facts=[
                SerializedFact(
                    fact_id="fact_1",
                    statement="FACT 1: (patient) -[has_symptom:0.80]-> (fever)",
                    path_id="path_1",
                    edge_ids=["edge_1"],
                    rel_type="has_symptom",
                    weight=0.80,
                ),
            ],
            markdown="FACT 1: (patient) -[has_symptom:0.80]-> (fever)",
            latency_ms=10.0,
        )

        mining_result = MiningResult(
            intent="information_lookup",
            entities=[MinedEntity(entity_id="patient", entity_type="OBJECT", confidence=0.90)],
            latency_ms=5.0,
        )

        # Act
        result = pipeline._synthesize(
            serialization_result=serialization_result,
            mining_result=mining_result,
            tenant_id="tenant-123",
            evidence_context=None,
        )

        # Assert
        assert result.response_text is not None
        assert "Grounded summary" in result.response_text
        assert "FACT 1" in result.response_text

    def test_synthesize_with_vertex_empty_facts(self) -> None:
        """_synthesize_with_vertex should handle empty facts gracefully."""
        # Arrange
        config = MindMapConfig()
        mock_spanner_client = Mock()
        pipeline = MindMapPipeline(config=config, spanner_client=mock_spanner_client)

        serialization_result = SerializationResult(
            facts=[],
            markdown="",
            latency_ms=10.0,
        )

        mining_result = MiningResult(
            intent="information_lookup",
            entities=[MinedEntity(entity_id="patient", entity_type="OBJECT", confidence=0.90)],
            latency_ms=5.0,
        )

        mock_evidence_context = EvidenceContext(
            items=[],
            total_items=0,
            total_chars=0,
            path_count=0,
            neighbor_count=0,
            is_empty=True,
            is_sufficient=False,
            insufficient_reasons=[EvidenceInsufficientReason.EMPTY_GRAPH],
            retrieval_latency_ms=25.0,
        )

        # Act
        result = pipeline._synthesize_with_vertex(
            serialization_result=serialization_result,
            mining_result=mining_result,
            tenant_id="tenant-123",
            evidence_context=mock_evidence_context,
        )

        # Assert
        assert result.response_text == pipeline.INSUFFICIENT_EVIDENCE_RESPONSE
        assert result.claim_fact_ids == []


class TestEvidenceSummaryGeneration:
    """Test EvidenceSummary generation from EvidenceContext."""

    def test_evidence_summary_from_context(self) -> None:
        """EvidenceSummary should accurately reflect EvidenceContext."""
        # Arrange
        now = datetime.now(UTC)
        evidence_context = EvidenceContext(
            items=[
                EvidenceItem(
                    evidence_id="evid_1",
                    source_type=EvidenceSourceType.PATH_BASED,
                    evidence_number=1,
                    graph_path="patient->has_symptom->fever",
                    serialized_form="patient->has_symptom->fever",
                    access_timestamp=now,
                    cognitive_weight=1.0,
                ),
                EvidenceItem(
                    evidence_id="evid_2",
                    source_type=EvidenceSourceType.NEIGHBOR_BASED,
                    evidence_number=2,
                    graph_path="patient->has_symptom->cough",
                    serialized_form="patient->has_symptom->cough",
                    access_timestamp=now,
                    cognitive_weight=1.0,
                ),
            ],
            total_items=EVIDENCE_SUMMARY_TOTAL_ITEMS,
            total_chars=60,
            path_count=1,
            neighbor_count=1,
            is_empty=False,
            is_sufficient=True,
            insufficient_reasons=[],
            retrieval_latency_ms=EVIDENCE_SUMMARY_LATENCY_MS,
        )

        # Act
        summary = EvidenceSummary(
            total_items=evidence_context.total_items,
            path_count=evidence_context.path_count,
            neighbor_count=evidence_context.neighbor_count,
            is_sufficient=evidence_context.is_sufficient,
            is_empty=evidence_context.is_empty,
            insufficient_reasons=evidence_context.insufficient_reasons,
            retrieval_latency_ms=evidence_context.retrieval_latency_ms,
        )

        # Assert
        assert summary.total_items == EVIDENCE_SUMMARY_TOTAL_ITEMS
        assert summary.path_count == EVIDENCE_SUMMARY_PATH_COUNT
        assert summary.neighbor_count == EVIDENCE_SUMMARY_NEIGHBOR_COUNT
        assert summary.is_sufficient is True
        assert summary.is_empty is False
        assert len(summary.insufficient_reasons) == 0
        assert summary.retrieval_latency_ms == EVIDENCE_SUMMARY_LATENCY_MS

    def test_evidence_summary_insufficient_signals(self) -> None:
        """EvidenceSummary should capture all insufficiency reasons."""
        # Arrange
        evidence_context = EvidenceContext(
            items=[],
            total_items=0,
            total_chars=0,
            path_count=0,
            neighbor_count=0,
            is_empty=True,
            is_sufficient=False,
            insufficient_reasons=[
                EvidenceInsufficientReason.NO_PATHS_FOUND,
                EvidenceInsufficientReason.AUTHORIZATION_DENIED,
            ],
            retrieval_latency_ms=10.0,
        )

        # Act
        summary = EvidenceSummary(
            total_items=evidence_context.total_items,
            path_count=evidence_context.path_count,
            neighbor_count=evidence_context.neighbor_count,
            is_sufficient=evidence_context.is_sufficient,
            is_empty=evidence_context.is_empty,
            insufficient_reasons=evidence_context.insufficient_reasons,
            retrieval_latency_ms=evidence_context.retrieval_latency_ms,
        )

        # Assert
        assert summary.is_sufficient is False
        assert EvidenceInsufficientReason.NO_PATHS_FOUND in summary.insufficient_reasons
        assert EvidenceInsufficientReason.AUTHORIZATION_DENIED in summary.insufficient_reasons
