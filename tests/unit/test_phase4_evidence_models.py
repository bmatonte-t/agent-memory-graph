"""Unit tests for Phase 4 evidence models and sufficiency heuristic."""

from datetime import datetime, timezone

import pytest

from src.memory.evidence_service import EvidenceSufficiencyHeuristic
from src.models.evidence import (
    EvidenceContext,
    EvidenceInsufficientReason,
    EvidenceItem,
    EvidenceSourceType,
    EvidenceSummary,
)


class TestEvidenceSourceType:
    """Tests for EvidenceSourceType enum."""

    def test_source_type_variants(self) -> None:
        """Verify all expected source type variants exist."""
        assert EvidenceSourceType.PATH_BASED == "path_based"
        assert EvidenceSourceType.NEIGHBOR_BASED == "neighbor_based"
        assert EvidenceSourceType.HYBRID == "hybrid"
        assert EvidenceSourceType.UNKNOWN == "unknown"


class TestEvidenceInsufficientReason:
    """Tests for EvidenceInsufficientReason enum."""

    def test_insufficient_reason_variants(self) -> None:
        """Verify all expected insufficient reason variants exist."""
        assert EvidenceInsufficientReason.NO_PATHS_FOUND == "no_paths_found"
        assert EvidenceInsufficientReason.NO_NEIGHBORS_FOUND == "no_neighbors_found"
        assert EvidenceInsufficientReason.TOKEN_BUDGET_EXCEEDED == "token_budget_exceeded"
        assert EvidenceInsufficientReason.AUTHORIZATION_DENIED == "authorization_denied"
        assert EvidenceInsufficientReason.TIMEOUT == "timeout"
        assert EvidenceInsufficientReason.EMPTY_GRAPH == "empty_graph"


class TestEvidenceItem:
    """Tests for EvidenceItem model."""

    def test_evidence_item_creation(self) -> None:
        """Create valid EvidenceItem."""
        now = datetime.now(timezone.utc)
        item = EvidenceItem(
            evidence_id="12345678-1234-5678-1234-567812345678",
            source_type=EvidenceSourceType.PATH_BASED,
            evidence_number=1,
            graph_path="patient->has_symptom->hoarse_voice",
            serialized_form="Patient has symptom hoarse voice",
            access_timestamp=now,
        )

        assert item.evidence_id == "12345678-1234-5678-1234-567812345678"
        assert item.source_type == EvidenceSourceType.PATH_BASED
        assert item.evidence_number == 1
        assert item.graph_path == "patient->has_symptom->hoarse_voice"
        assert item.serialized_form == "Patient has symptom hoarse voice"
        assert item.cognitive_weight == 1.0  # default

    def test_evidence_item_minimal(self) -> None:
        """Create EvidenceItem with minimal fields."""
        now = datetime.now(timezone.utc)
        item = EvidenceItem(
            evidence_id="test-id",
            source_type=EvidenceSourceType.NEIGHBOR_BASED,
            evidence_number=1,
            graph_path="entity->rel->neighbor",
            access_timestamp=now,
        )

        assert item.evidence_id == "test-id"
        assert item.serialized_form is None
        assert item.audit_log_ref is None

    def test_evidence_item_cognitive_weight_bounds(self) -> None:
        """Cognitive weight must be between 0.0 and 10.0."""
        now = datetime.now(timezone.utc)

        # Valid: 0.0
        item = EvidenceItem(
            evidence_id="id",
            source_type=EvidenceSourceType.PATH_BASED,
            evidence_number=1,
            graph_path="path",
            access_timestamp=now,
            cognitive_weight=0.0,
        )
        assert item.cognitive_weight == 0.0

        # Valid: 10.0
        item = EvidenceItem(
            evidence_id="id",
            source_type=EvidenceSourceType.PATH_BASED,
            evidence_number=1,
            graph_path="path",
            access_timestamp=now,
            cognitive_weight=10.0,
        )
        assert item.cognitive_weight == 10.0

        # Invalid: > 10.0
        with pytest.raises(ValueError):
            EvidenceItem(
                evidence_id="id",
                source_type=EvidenceSourceType.PATH_BASED,
                evidence_number=1,
                graph_path="path",
                access_timestamp=now,
                cognitive_weight=10.1,
            )


class TestEvidenceContext:
    """Tests for EvidenceContext model."""

    def test_evidence_context_empty(self) -> None:
        """Create empty EvidenceContext (no evidence retrieved)."""
        ctx = EvidenceContext(
            is_empty=True,
            insufficient_reasons=[EvidenceInsufficientReason.NO_PATHS_FOUND],
        )

        assert ctx.items == []
        assert ctx.total_items == 0
        assert ctx.is_empty is True
        assert ctx.is_sufficient is False
        assert EvidenceInsufficientReason.NO_PATHS_FOUND in ctx.insufficient_reasons

    def test_evidence_context_with_items(self) -> None:
        """Create EvidenceContext with retrieved items."""
        now = datetime.now(timezone.utc)
        item1 = EvidenceItem(
            evidence_id="id-1",
            source_type=EvidenceSourceType.PATH_BASED,
            evidence_number=1,
            graph_path="path1",
            access_timestamp=now,
        )
        item2 = EvidenceItem(
            evidence_id="id-2",
            source_type=EvidenceSourceType.NEIGHBOR_BASED,
            evidence_number=1,
            graph_path="entity->rel->neighbor1,neighbor2",
            access_timestamp=now,
        )

        ctx = EvidenceContext(
            items=[item1, item2],
            total_items=2,
            total_chars=100,
            path_count=1,
            neighbor_count=1,
            is_empty=False,
            is_sufficient=True,
        )

        assert len(ctx.items) == 2
        assert ctx.total_items == 2
        assert ctx.path_count == 1
        assert ctx.neighbor_count == 1
        assert ctx.is_sufficient is True

    def test_evidence_context_defaults(self) -> None:
        """Verify EvidenceContext defaults."""
        ctx = EvidenceContext()

        assert ctx.items == []
        assert ctx.total_items == 0
        assert ctx.total_chars == 0
        assert ctx.path_count == 0
        assert ctx.neighbor_count == 0
        assert ctx.is_empty is False
        assert ctx.is_sufficient is False
        assert ctx.insufficient_reasons == []
        assert ctx.retrieval_latency_ms == 0.0


class TestEvidenceSummary:
    """Tests for EvidenceSummary model."""

    def test_evidence_summary_creation(self) -> None:
        """Create EvidenceSummary for response payload."""
        summary = EvidenceSummary(
            total_items=5,
            path_count=2,
            neighbor_count=3,
            is_sufficient=True,
            retrieval_latency_ms=150.5,
        )

        assert summary.total_items == 5
        assert summary.path_count == 2
        assert summary.neighbor_count == 3
        assert summary.is_sufficient is True
        assert summary.is_empty is False
        assert summary.retrieval_latency_ms == 150.5

    def test_evidence_summary_insufficient(self) -> None:
        """Create EvidenceSummary indicating insufficient evidence."""
        summary = EvidenceSummary(
            total_items=0,
            path_count=0,
            neighbor_count=0,
            is_sufficient=False,
            is_empty=True,
            insufficient_reasons=[EvidenceInsufficientReason.NO_PATHS_FOUND],
        )

        assert summary.is_empty is True
        assert summary.is_sufficient is False
        assert len(summary.insufficient_reasons) == 1


class TestEvidenceSufficiencyHeuristic:
    """Tests for EvidenceSufficiencyHeuristic."""

    def test_sufficient_when_both_types_available(self) -> None:
        """Sufficient if both path and neighbor evidence present."""
        assert EvidenceSufficiencyHeuristic.is_sufficient(1, 1) is True
        assert EvidenceSufficiencyHeuristic.is_sufficient(2, 1) is True
        assert EvidenceSufficiencyHeuristic.is_sufficient(1, 2) is True

    def test_sufficient_when_abundant_single_type(self) -> None:
        """Sufficient if either type has >= 3 items."""
        assert EvidenceSufficiencyHeuristic.is_sufficient(3, 0) is True
        assert EvidenceSufficiencyHeuristic.is_sufficient(5, 0) is True
        assert EvidenceSufficiencyHeuristic.is_sufficient(0, 3) is True
        assert EvidenceSufficiencyHeuristic.is_sufficient(0, 10) is True

    def test_insufficient_when_neither_criteria_met(self) -> None:
        """Insufficient if neither criteria satisfied."""
        assert EvidenceSufficiencyHeuristic.is_sufficient(0, 0) is False
        assert EvidenceSufficiencyHeuristic.is_sufficient(1, 0) is False
        assert EvidenceSufficiencyHeuristic.is_sufficient(0, 1) is False
        # (2, 1) has both types, so it's sufficient
        assert EvidenceSufficiencyHeuristic.is_sufficient(2, 1) is True
        assert EvidenceSufficiencyHeuristic.is_sufficient(1, 2) is True
        # These have only 2 of one type (insufficient without other type or >= 3 of one type)
        assert EvidenceSufficiencyHeuristic.is_sufficient(2, 0) is False
        assert EvidenceSufficiencyHeuristic.is_sufficient(0, 2) is False

    def test_insufficient_reasons_empty_graph(self) -> None:
        """When graph is empty, return EMPTY_GRAPH reason."""
        reasons = EvidenceSufficiencyHeuristic.insufficient_reasons(
            path_count=0,
            neighbor_count=0,
            graph_empty=True,
        )

        assert len(reasons) == 1
        assert EvidenceInsufficientReason.EMPTY_GRAPH in reasons

    def test_insufficient_reasons_no_paths_or_neighbors(self) -> None:
        """When no evidence retrieved, list reasons why."""
        reasons = EvidenceSufficiencyHeuristic.insufficient_reasons(
            path_count=0,
            neighbor_count=0,
            had_path_timeout=False,
            had_neighbor_timeout=False,
            had_auth_denied=False,
            graph_empty=False,
        )

        assert EvidenceInsufficientReason.NO_PATHS_FOUND in reasons
        assert EvidenceInsufficientReason.NO_NEIGHBORS_FOUND in reasons

    def test_insufficient_reasons_timeout(self) -> None:
        """When retrieval times out, identify which operation."""
        # Path timeout only
        reasons = EvidenceSufficiencyHeuristic.insufficient_reasons(
            path_count=0,
            neighbor_count=0,
            had_path_timeout=True,
            had_neighbor_timeout=False,
        )
        assert EvidenceInsufficientReason.TIMEOUT in reasons
        assert EvidenceInsufficientReason.NO_NEIGHBORS_FOUND not in reasons

        # Both timeout
        reasons = EvidenceSufficiencyHeuristic.insufficient_reasons(
            path_count=0,
            neighbor_count=0,
            had_path_timeout=True,
            had_neighbor_timeout=True,
        )
        assert EvidenceInsufficientReason.TIMEOUT in reasons
        assert len(reasons) == 1  # single TIMEOUT reason, not duplicated

    def test_insufficient_reasons_authorization_denied(self) -> None:
        """When authorization denied, identify that reason."""
        reasons = EvidenceSufficiencyHeuristic.insufficient_reasons(
            path_count=0,
            neighbor_count=0,
            had_auth_denied=True,
        )

        assert EvidenceInsufficientReason.AUTHORIZATION_DENIED in reasons
