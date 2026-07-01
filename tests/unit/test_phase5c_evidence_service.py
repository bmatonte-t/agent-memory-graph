"""Unit tests for Phase 5C Evidence Service enrichment with freshness and aggregation."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from src.memory.evidence_service import EvidenceService
from src.models.evidence import (
    EvidenceContext,
    EvidenceInsufficientReason,
    EvidenceItem,
    EvidenceSourceType,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

# Test constants
TEST_TENANT_ID = "tenant_a"
FRESHNESS_DECAY_LAMBDA = 0.1
HIGH_CONFIDENCE = 0.9
MEDIUM_CONFIDENCE = 0.7
LOW_CONFIDENCE = 0.3
DEFAULT_CONFIDENCE = 1.0
FRESHNESS_NEW_THRESHOLD = 0.99
FRESHNESS_7H_MIN = 0.49
FRESHNESS_7H_MAX = 0.51
FRESHNESS_STALE_THRESHOLD = 0.1
FRESHNESS_AVG_7H_5H = 0.745
FRESHNESS_AVG_7H_5H_RANGE = 0.005
CONFLICT_COUNT_TWO = 2

CONFIDENCE_AVG_THREE_ITEMS = 0.633
CONFIDENCE_AVG_RANGE = 0.005
SUMMARY_ITEM_COUNT_TWO = 2
SUMMARY_WARNING_COUNT_ONE = 1


class TestPhase5CFreshnessComputation:
    """Test suite for Phase 5C freshness score computation."""

    def test_freshness_newly_created_evidence_scores_high(self) -> None:
        """Newly created evidence should score near 1.0."""
        client = MagicMock()
        service = EvidenceService(client)

        now = datetime.now(UTC)
        items = [
            EvidenceItem(
                evidence_id="evid_1",
                source_type=EvidenceSourceType.PATH_BASED,
                evidence_number=1,
                graph_path="path_1",
                access_timestamp=now,
                source_confidence_score=HIGH_CONFIDENCE,
            ),
        ]

        service._compute_freshness_scores(items, freshness_decay_lambda=FRESHNESS_DECAY_LAMBDA)

        assert items[0].freshness_score is not None
        assert items[0].freshness_score > FRESHNESS_NEW_THRESHOLD

    def test_freshness_7_hours_old_decays_correctly(self) -> None:
        """Evidence 7 hours old should decay to ~0.497 with λ=0.1."""
        client = MagicMock()
        service = EvidenceService(client)

        now = datetime.now(UTC)
        seven_hours_ago = now - timedelta(hours=7)
        items = [
            EvidenceItem(
                evidence_id="evid_1",
                source_type=EvidenceSourceType.PATH_BASED,
                evidence_number=1,
                graph_path="path_1",
                access_timestamp=seven_hours_ago,
                source_confidence_score=HIGH_CONFIDENCE,
            ),
        ]

        service._compute_freshness_scores(items, freshness_decay_lambda=FRESHNESS_DECAY_LAMBDA)

        assert items[0].freshness_score is not None
        assert FRESHNESS_7H_MIN < items[0].freshness_score < FRESHNESS_7H_MAX

    def test_freshness_24_hours_old_decays_significantly(self) -> None:
        """Evidence 24 hours old should decay substantially."""
        client = MagicMock()
        service = EvidenceService(client)

        now = datetime.now(UTC)
        day_ago = now - timedelta(hours=24)
        items = [
            EvidenceItem(
                evidence_id="evid_1",
                source_type=EvidenceSourceType.PATH_BASED,
                evidence_number=1,
                graph_path="path_1",
                access_timestamp=day_ago,
                source_confidence_score=HIGH_CONFIDENCE,
            ),
        ]

        service._compute_freshness_scores(items, freshness_decay_lambda=FRESHNESS_DECAY_LAMBDA)

        assert items[0].freshness_score is not None
        assert items[0].freshness_score < FRESHNESS_STALE_THRESHOLD

    def test_freshness_multiple_items_computed_independently(self) -> None:
        """Multiple items with different ages should compute independently."""
        client = MagicMock()
        service = EvidenceService(client)

        now = datetime.now(UTC)
        items = [
            EvidenceItem(
                evidence_id="evid_1",
                source_type=EvidenceSourceType.PATH_BASED,
                evidence_number=1,
                graph_path="path_1",
                access_timestamp=now,
                source_confidence_score=HIGH_CONFIDENCE,
            ),
            EvidenceItem(
                evidence_id="evid_2",
                source_type=EvidenceSourceType.NEIGHBOR_BASED,
                evidence_number=2,
                graph_path="path_2",
                access_timestamp=now - timedelta(hours=12),
                source_confidence_score=MEDIUM_CONFIDENCE,
            ),
        ]

        service._compute_freshness_scores(items, freshness_decay_lambda=FRESHNESS_DECAY_LAMBDA)

        assert items[0].freshness_score is not None
        assert items[1].freshness_score is not None
        assert items[0].freshness_score > items[1].freshness_score


class TestPhase5CConfidenceAggregation:
    """Test suite for Phase 5C confidence score aggregation."""

    def test_confidence_aggregation_empty_items_returns_defaults(self) -> None:
        """Empty items should return default high confidence."""
        client = MagicMock()
        service = EvidenceService(client)

        min_conf, avg_conf = service._aggregate_confidence_scores([])

        assert min_conf == 1.0
        assert avg_conf == 1.0

    def test_confidence_aggregation_single_item(self) -> None:
        """Single item should return its confidence for both min and avg."""
        client = MagicMock()
        service = EvidenceService(client)

        items = [
            EvidenceItem(
                evidence_id="evid_1",
                source_type=EvidenceSourceType.PATH_BASED,
                evidence_number=1,
                graph_path="path_1",
                access_timestamp=datetime.now(UTC),
                source_confidence_score=MEDIUM_CONFIDENCE,
            ),
        ]

        min_conf, avg_conf = service._aggregate_confidence_scores(items)

        assert min_conf == MEDIUM_CONFIDENCE
        assert avg_conf == MEDIUM_CONFIDENCE

    def test_confidence_aggregation_finds_minimum(self) -> None:
        """Minimum confidence should be the bottleneck across items."""
        client = MagicMock()
        service = EvidenceService(client)

        items = [
            EvidenceItem(
                evidence_id="evid_1",
                source_type=EvidenceSourceType.PATH_BASED,
                evidence_number=1,
                graph_path="path_1",
                access_timestamp=datetime.now(UTC),
                source_confidence_score=HIGH_CONFIDENCE,
            ),
            EvidenceItem(
                evidence_id="evid_2",
                source_type=EvidenceSourceType.NEIGHBOR_BASED,
                evidence_number=2,
                graph_path="path_2",
                access_timestamp=datetime.now(UTC),
                source_confidence_score=LOW_CONFIDENCE,
            ),
            EvidenceItem(
                evidence_id="evid_3",
                source_type=EvidenceSourceType.PATH_BASED,
                evidence_number=3,
                graph_path="path_3",
                access_timestamp=datetime.now(UTC),
                source_confidence_score=MEDIUM_CONFIDENCE,
            ),
        ]

        min_conf, avg_conf = service._aggregate_confidence_scores(items)

        assert min_conf == LOW_CONFIDENCE
        assert (
            CONFIDENCE_AVG_THREE_ITEMS - CONFIDENCE_AVG_RANGE
            < avg_conf
            < CONFIDENCE_AVG_THREE_ITEMS + CONFIDENCE_AVG_RANGE
        )


class TestPhase5CContradictionAggregation:
    """Test suite for Phase 5C contradiction warning aggregation."""

    def test_contradiction_aggregation_empty_items_returns_empty(self) -> None:
        """Empty items should return no contradictions."""
        client = MagicMock()
        service = EvidenceService(client)

        warnings = service._aggregate_contradiction_warnings([])

        assert warnings == []

    def test_contradiction_aggregation_no_flags_returns_empty(self) -> None:
        """Items with no flags should return no contradictions."""
        client = MagicMock()
        service = EvidenceService(client)

        items = [
            EvidenceItem(
                evidence_id="evid_1",
                source_type=EvidenceSourceType.PATH_BASED,
                evidence_number=1,
                graph_path="path_1",
                access_timestamp=datetime.now(UTC),
                contradiction_flags=[],
            ),
        ]

        warnings = service._aggregate_contradiction_warnings(items)

        assert warnings == []

    def test_contradiction_aggregation_groups_by_severity(self) -> None:
        """Contradictions should be grouped by severity level."""
        client = MagicMock()
        service = EvidenceService(client)

        items = [
            EvidenceItem(
                evidence_id="evid_1",
                source_type=EvidenceSourceType.PATH_BASED,
                evidence_number=1,
                graph_path="path_1",
                access_timestamp=datetime.now(UTC),
                contradiction_flags=["high:node_1", "high:node_2"],
            ),
            EvidenceItem(
                evidence_id="evid_2",
                source_type=EvidenceSourceType.NEIGHBOR_BASED,
                evidence_number=2,
                graph_path="path_2",
                access_timestamp=datetime.now(UTC),
                contradiction_flags=["medium:node_3"],
            ),
        ]

        warnings = service._aggregate_contradiction_warnings(items)

        assert len(warnings) == CONFLICT_COUNT_TWO
        high_warning = next((w for w in warnings if w["severity"] == "high"), None)
        assert high_warning is not None
        assert high_warning["conflicting_count"] == CONFLICT_COUNT_TWO
        assert set(high_warning["nodes"]) == {"node_1", "node_2"}

    def test_contradiction_aggregation_handles_unstructured_flags(self) -> None:
        """Unstructured flags should default to medium severity."""
        client = MagicMock()
        service = EvidenceService(client)

        items = [
            EvidenceItem(
                evidence_id="evid_1",
                source_type=EvidenceSourceType.PATH_BASED,
                evidence_number=1,
                graph_path="path_1",
                access_timestamp=datetime.now(UTC),
                contradiction_flags=["conflict_detected", "anomaly_flag"],
            ),
        ]

        warnings = service._aggregate_contradiction_warnings(items)

        assert len(warnings) == SUMMARY_WARNING_COUNT_ONE
        assert warnings[0]["severity"] == "medium"
        assert warnings[0]["conflicting_count"] == CONFLICT_COUNT_TWO


class TestPhase5CEnrichmentAndSummary:
    """Test suite for Phase 5C evidence enrichment and summary building."""

    def test_enrich_evidence_context_with_phase5_computes_freshness(self) -> None:
        """Enrichment should compute freshness scores for all items."""
        client = MagicMock()
        service = EvidenceService(client)

        now = datetime.now(UTC)
        context = EvidenceContext(
            items=[
                EvidenceItem(
                    evidence_id="evid_1",
                    source_type=EvidenceSourceType.PATH_BASED,
                    evidence_number=1,
                    graph_path="path_1",
                    access_timestamp=now - timedelta(hours=5),
                    source_confidence_score=HIGH_CONFIDENCE,
                ),
                EvidenceItem(
                    evidence_id="evid_2",
                    source_type=EvidenceSourceType.NEIGHBOR_BASED,
                    evidence_number=2,
                    graph_path="path_2",
                    access_timestamp=now - timedelta(hours=12),
                    source_confidence_score=MEDIUM_CONFIDENCE,
                ),
            ],
            total_items=SUMMARY_ITEM_COUNT_TWO,
            is_sufficient=True,
        )

        service.enrich_evidence_context_with_phase5(
            context,
            freshness_decay_lambda=FRESHNESS_DECAY_LAMBDA,
        )

        assert context.items[0].freshness_score is not None
        assert context.items[1].freshness_score is not None
        assert context.items[0].freshness_score > context.items[1].freshness_score

    def test_build_evidence_summary_includes_phase5_signals(self) -> None:
        """Summary should include min confidence and average freshness."""
        client = MagicMock()
        service = EvidenceService(client)

        now = datetime.now(UTC)
        context = EvidenceContext(
            items=[
                EvidenceItem(
                    evidence_id="evid_1",
                    source_type=EvidenceSourceType.PATH_BASED,
                    evidence_number=1,
                    graph_path="path_1",
                    access_timestamp=now,
                    source_confidence_score=HIGH_CONFIDENCE,
                    freshness_score=0.95,
                    contradiction_flags=[],
                ),
                EvidenceItem(
                    evidence_id="evid_2",
                    source_type=EvidenceSourceType.NEIGHBOR_BASED,
                    evidence_number=2,
                    graph_path="path_2",
                    access_timestamp=now - timedelta(hours=6),
                    source_confidence_score=LOW_CONFIDENCE,
                    freshness_score=0.54,
                    contradiction_flags=["high:node_1"],
                ),
            ],
            total_items=SUMMARY_ITEM_COUNT_TWO,
            path_count=1,
            neighbor_count=1,
            is_sufficient=True,
        )

        summary = service.build_evidence_summary(context)

        assert summary.total_items == SUMMARY_ITEM_COUNT_TWO
        assert summary.min_confidence_in_set == LOW_CONFIDENCE
        assert summary.average_freshness is not None
        assert (
            FRESHNESS_AVG_7H_5H - FRESHNESS_AVG_7H_5H_RANGE
            < summary.average_freshness
            < FRESHNESS_AVG_7H_5H + FRESHNESS_AVG_7H_5H_RANGE
        )
        assert len(summary.contradiction_warnings) == SUMMARY_WARNING_COUNT_ONE

    def test_build_evidence_summary_empty_context_has_defaults(self) -> None:
        """Empty context should return sensible defaults in summary."""
        client = MagicMock()
        service = EvidenceService(client)

        context = EvidenceContext(
            items=[],
            total_items=0,
            is_empty=True,
            insufficient_reasons=[EvidenceInsufficientReason.EMPTY_GRAPH],
        )

        summary = service.build_evidence_summary(context)

        assert summary.total_items == 0
        assert summary.is_empty is True
        assert summary.min_confidence_in_set == 1.0
        assert summary.average_freshness is None
        assert summary.contradiction_warnings == []


class TestOperationalEvidenceQueries:
    """Test suite for operational evidence queries (Phase 4D diagnostics)."""

    async def test_get_evidence_context_for_tenant_returns_recent_items(
        self,
    ) -> None:
        """Should retrieve recent evidence items for a tenant."""

        @contextmanager
        def mock_snapshot_context() -> Iterator[MagicMock]:
            """Mock snapshot context manager."""
            yield mock_snapshot

        client = MagicMock()
        service = EvidenceService(client)

        now = datetime.now(UTC)
        recent_time = now - timedelta(hours=2)

        # Mock database rows
        mock_rows = [
            (
                "evid_1",
                "path_based",
                1,
                "entity1->rel1->entity2",
                "Evidence 1",
                recent_time,
                1.0,
                "audit_1",
                recent_time,
            ),
        ]

        mock_snapshot = MagicMock()
        mock_snapshot.execute_sql.return_value = mock_rows

        mock_db = MagicMock()
        mock_db.snapshot = mock_snapshot_context

        with patch(
            "src.memory.evidence_service.SpannerClient.get_database",
            return_value=mock_db,
        ):
            items = await service.get_evidence_context_for_tenant("tenant_a", limit_hours=24)

        assert len(items) == 1
        assert items[0].evidence_id == "evid_1"
        assert items[0].source_type == EvidenceSourceType.PATH_BASED
        assert items[0].evidence_number == 1
        mock_snapshot.execute_sql.assert_called_once()

    async def test_get_evidence_context_for_tenant_filters_by_time(
        self,
    ) -> None:
        """Should filter evidence by cutoff time."""

        @contextmanager
        def mock_snapshot_context() -> Iterator[MagicMock]:
            """Mock snapshot context manager."""
            yield mock_snapshot

        client = MagicMock()
        service = EvidenceService(client)

        mock_snapshot = MagicMock()
        mock_snapshot.execute_sql.return_value = []

        mock_db = MagicMock()
        mock_db.snapshot = mock_snapshot_context

        with patch(
            "src.memory.evidence_service.SpannerClient.get_database",
            return_value=mock_db,
        ):
            await service.get_evidence_context_for_tenant("tenant_a", limit_hours=12)

        # Verify the query was called with cutoff time calculation
        call_args = mock_snapshot.execute_sql.call_args
        assert call_args is not None
        assert "CreatedAt > @cutoff_time" in call_args[0][0]

    async def test_get_evidence_context_for_tenant_empty_result(self) -> None:
        """Should return empty list when no recent evidence found."""

        @contextmanager
        def mock_snapshot_context() -> Iterator[MagicMock]:
            """Mock snapshot context manager."""
            yield mock_snapshot

        client = MagicMock()
        service = EvidenceService(client)

        mock_snapshot = MagicMock()
        mock_snapshot.execute_sql.return_value = []

        mock_db = MagicMock()
        mock_db.snapshot = mock_snapshot_context

        with patch(
            "src.memory.evidence_service.SpannerClient.get_database",
            return_value=mock_db,
        ):
            items = await service.get_evidence_context_for_tenant("tenant_a")

        assert len(items) == 0

    async def test_get_evidence_context_for_tenant_raises_on_query_error(
        self,
    ) -> None:
        """Should raise RuntimeError if database query fails."""

        @contextmanager
        def mock_snapshot_context() -> Iterator[MagicMock]:
            """Mock snapshot context manager."""
            yield mock_snapshot

        client = MagicMock()
        service = EvidenceService(client)

        mock_snapshot = MagicMock()
        mock_snapshot.execute_sql.side_effect = RuntimeError("Connection failed")

        mock_db = MagicMock()
        mock_db.snapshot = mock_snapshot_context

        with (
            patch(
                "src.memory.evidence_service.SpannerClient.get_database",
                return_value=mock_db,
            ),
            pytest.raises(RuntimeError, match="get_evidence_context_for_tenant failed"),
        ):
            await service.get_evidence_context_for_tenant("tenant_a")


class TestFreshnessScoreValidation:
    """Validate that FreshnessScore enforces decay_lambda bounds."""

    def test_freshness_score_rejects_decay_lambda_above_one(self) -> None:
        """decay_lambda > 1.0 must raise ValidationError."""
        from pydantic import ValidationError

        from src.models.confidence import FreshnessScore

        with pytest.raises(ValidationError):
            FreshnessScore(decay_lambda=5.0, hours_old=10, current_score=0.5)

    def test_freshness_score_rejects_decay_lambda_below_minimum(self) -> None:
        """decay_lambda < 0.01 must raise ValidationError."""
        from pydantic import ValidationError

        from src.models.confidence import FreshnessScore

        with pytest.raises(ValidationError):
            FreshnessScore(decay_lambda=0.0, hours_old=10, current_score=0.5)

    def test_freshness_score_accepts_valid_decay_lambda(self) -> None:
        """decay_lambda within [0.01, 1.0] must not raise."""
        from src.models.confidence import FreshnessScore

        score = FreshnessScore(decay_lambda=0.1, hours_old=7.0, current_score=0.5)
        assert score.decay_lambda == 0.1

    def test_freshness_score_accepts_boundary_values(self) -> None:
        """Boundary values 0.01 and 1.0 must both be accepted."""
        from src.models.confidence import FreshnessScore

        low = FreshnessScore(decay_lambda=0.01, hours_old=0.0, current_score=1.0)
        high = FreshnessScore(decay_lambda=1.0, hours_old=0.0, current_score=1.0)
        assert low.decay_lambda == 0.01
        assert high.decay_lambda == 1.0
