"""Unit tests for Phase 5B ingest metadata capture and contradiction detection."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.schema import SchemaConfig
from src.memory.api import MemoryAPI
from src.models.schemas import FactResponse

# Test constants
TEST_TENANT_ID = "tenant_a"
TEST_ENTITY_ID = "ent_123"
TEST_ENTITY_TYPE = "PERSON"
TEST_SESSION_ID = "sess_1"
TEST_AGENT_ID = "agent_001"
TEST_QUERY_ID = "query_456"
TEST_CONFIDENCE_SCORE = 0.85
API_DERIVED_CONFIDENCE_SCORE = 0.7
DEFAULT_CONFIDENCE_SCORE = 1.0
DEFAULT_WEIGHT = 0.5
NUM_CONTRADICTIONS_MULTIPLE = 2


class TestPhase5BContradictionDetection:
    """Test suite for Phase 5B contradiction detection heuristics."""

    def test_detect_contradictions_empty_attributes_returns_empty_list(self) -> None:
        """Empty attributes should return no contradictions."""
        result = MemoryAPI._detect_contradictions(
            tenant_id=TEST_TENANT_ID,
            entity_id=TEST_ENTITY_ID,
            entity_type=TEST_ENTITY_TYPE,
            attributes=None,
        )
        assert result == []

    def test_detect_contradictions_finds_explicit_conflicts_with_marker(self) -> None:
        """Explicit conflicts_with marker should be detected as high-severity."""
        attributes = {"conflicts_with": ["node_456", "node_789"]}

        result = MemoryAPI._detect_contradictions(
            tenant_id=TEST_TENANT_ID,
            entity_id=TEST_ENTITY_ID,
            entity_type=TEST_ENTITY_TYPE,
            attributes=attributes,
        )

        assert len(result) == 1
        assert result[0]["severity"] == "high"
        assert result[0]["detected_by"] == "explicit_conflicts_with_marker"
        assert set(result[0]["conflicting_node_ids"]) == {"node_456", "node_789"}

    def test_detect_contradictions_finds_deprecated_recently_accessed_conflict(self) -> None:
        """Deprecated=True with recent access should flag medium-severity conflict."""
        now = datetime.now(UTC)
        recent_access = now.isoformat()

        attributes = {
            "is_deprecated": True,
            "last_access": recent_access,
        }

        result = MemoryAPI._detect_contradictions(
            tenant_id=TEST_TENANT_ID,
            entity_id=TEST_ENTITY_ID,
            entity_type=TEST_ENTITY_TYPE,
            attributes=attributes,
        )

        assert len(result) == 1
        assert result[0]["severity"] == "medium"
        assert result[0]["detected_by"] == "value_incompatibility"
        assert "deprecated" in result[0]["reason"].lower()

    def test_detect_contradictions_finds_is_active_status_mismatch(self) -> None:
        """is_active=False with active status should be flagged."""
        attributes = {
            "is_active": False,
            "status": "active",
        }

        result = MemoryAPI._detect_contradictions(
            tenant_id=TEST_TENANT_ID,
            entity_id=TEST_ENTITY_ID,
            entity_type=TEST_ENTITY_TYPE,
            attributes=attributes,
        )

        assert len(result) == 1
        assert result[0]["severity"] == "high"
        assert result[0]["detected_by"] == "value_incompatibility"
        assert "is_active" in result[0]["reason"]

    def test_detect_contradictions_ignores_invalid_timestamp(self) -> None:
        """Invalid timestamp formats should not crash the detector."""
        attributes = {
            "is_deprecated": True,
            "last_access": "not-a-date",
        }

        result = MemoryAPI._detect_contradictions(
            tenant_id=TEST_TENANT_ID,
            entity_id=TEST_ENTITY_ID,
            entity_type=TEST_ENTITY_TYPE,
            attributes=attributes,
        )

        # Should return empty list (no valid contradiction detected)
        assert result == []

    def test_detect_contradictions_returns_multiple_contradictions(self) -> None:
        """Multiple heuristics matching should return all contradictions."""
        attributes = {
            "conflicts_with": ["node_456"],
            "is_active": False,
            "status": "open",
        }

        result = MemoryAPI._detect_contradictions(
            tenant_id=TEST_TENANT_ID,
            entity_id=TEST_ENTITY_ID,
            entity_type=TEST_ENTITY_TYPE,
            attributes=attributes,
        )

        assert len(result) == NUM_CONTRADICTIONS_MULTIPLE
        # Should have explicit conflict and status mismatch
        detected_by = {c["detected_by"] for c in result}
        assert "explicit_conflicts_with_marker" in detected_by
        assert "value_incompatibility" in detected_by


class TestPhase5BSourceConfidenceInitialization:
    """Test suite for Phase 5B source confidence scoring."""

    @pytest.mark.asyncio
    async def test_add_semantic_fact_default_confidence_no_source(self) -> None:
        """Facts without source metadata should get default high confidence (1.0)."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_db.snapshot.return_value.__enter__.return_value = mock_snapshot
            mock_db.snapshot.return_value.__exit__.return_value = None
            mock_snapshot.execute_sql.return_value = [(SchemaConfig.MEMORY_TIER_SEMANTIC,)]
            mock_client.get_database.return_value = mock_db

            with (
                patch.object(
                    MemoryAPI,
                    "_increment_session_action_count",
                    return_value=1,
                ),
                patch.object(
                    MemoryAPI,
                    "_update_weight_on_successful_use",
                    new_callable=AsyncMock,
                ),
            ):
                response = await MemoryAPI.add_semantic_fact(
                    tenant_id=TEST_TENANT_ID,
                    entity_type=TEST_ENTITY_TYPE,
                    entity_id=TEST_ENTITY_ID,
                    attributes={"name": "John"},
                    session_id=TEST_SESSION_ID,
                )

            assert response.source_confidence_score == 1.0

    @pytest.mark.asyncio
    async def test_add_semantic_fact_api_derived_confidence(self) -> None:
        """Facts with source_agent_id should get API-derived confidence (0.7)."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_db.snapshot.return_value.__enter__.return_value = mock_snapshot
            mock_db.snapshot.return_value.__exit__.return_value = None
            mock_snapshot.execute_sql.return_value = [(SchemaConfig.MEMORY_TIER_SEMANTIC,)]
            mock_client.get_database.return_value = mock_db

            with (
                patch.object(
                    MemoryAPI,
                    "_increment_session_action_count",
                    return_value=1,
                ),
                patch.object(
                    MemoryAPI,
                    "_update_weight_on_successful_use",
                    new_callable=AsyncMock,
                ),
            ):
                response = await MemoryAPI.add_semantic_fact(
                    tenant_id=TEST_TENANT_ID,
                    entity_type=TEST_ENTITY_TYPE,
                    entity_id=TEST_ENTITY_ID,
                    attributes={"name": "John"},
                    session_id=TEST_SESSION_ID,
                    source_agent_id=TEST_AGENT_ID,
                )

            assert response.source_confidence_score == API_DERIVED_CONFIDENCE_SCORE


class TestPhase5BSourceMetadataStorage:
    """Test suite for Phase 5B source metadata storage and retrieval."""

    @pytest.mark.asyncio
    async def test_add_semantic_fact_stores_source_metadata(self) -> None:
        """Source metadata should be stored in FactResponse."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_db.snapshot.return_value.__enter__.return_value = mock_snapshot
            mock_db.snapshot.return_value.__exit__.return_value = None
            mock_snapshot.execute_sql.return_value = [(SchemaConfig.MEMORY_TIER_SEMANTIC,)]
            mock_client.get_database.return_value = mock_db

            with (
                patch.object(
                    MemoryAPI,
                    "_increment_session_action_count",
                    return_value=1,
                ),
                patch.object(
                    MemoryAPI,
                    "_update_weight_on_successful_use",
                    new_callable=AsyncMock,
                ),
            ):
                response = await MemoryAPI.add_semantic_fact(
                    tenant_id=TEST_TENANT_ID,
                    entity_type=TEST_ENTITY_TYPE,
                    entity_id=TEST_ENTITY_ID,
                    attributes={"name": "John"},
                    session_id=TEST_SESSION_ID,
                    source_agent_id=TEST_AGENT_ID,
                    source_query_id=TEST_QUERY_ID,
                )

            assert response.source_agent_id == TEST_AGENT_ID
            assert response.source_query_id == TEST_QUERY_ID

    @pytest.mark.asyncio
    async def test_add_semantic_fact_stores_contradictions_in_response(self) -> None:
        """Detected contradictions should be included in FactResponse."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_db.snapshot.return_value.__enter__.return_value = mock_snapshot
            mock_db.snapshot.return_value.__exit__.return_value = None
            mock_snapshot.execute_sql.return_value = [(SchemaConfig.MEMORY_TIER_SEMANTIC,)]
            mock_client.get_database.return_value = mock_db

            with (
                patch.object(
                    MemoryAPI,
                    "_increment_session_action_count",
                    return_value=1,
                ),
                patch.object(
                    MemoryAPI,
                    "_update_weight_on_successful_use",
                    new_callable=AsyncMock,
                ),
            ):
                response = await MemoryAPI.add_semantic_fact(
                    tenant_id=TEST_TENANT_ID,
                    entity_type=TEST_ENTITY_TYPE,
                    entity_id=TEST_ENTITY_ID,
                    attributes={
                        "name": "John",
                        "conflicts_with": ["node_456"],
                    },
                    session_id=TEST_SESSION_ID,
                )

            assert len(response.detected_contradictions) > 0
            assert response.detected_contradictions[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_add_semantic_fact_backward_compatible_no_source_metadata(
        self,
    ) -> None:
        """add_semantic_fact should work without source metadata (backward compatible)."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_db.snapshot.return_value.__enter__.return_value = mock_snapshot
            mock_db.snapshot.return_value.__exit__.return_value = None
            mock_snapshot.execute_sql.return_value = [(SchemaConfig.MEMORY_TIER_SEMANTIC,)]
            mock_client.get_database.return_value = mock_db

            with (
                patch.object(
                    MemoryAPI,
                    "_increment_session_action_count",
                    return_value=1,
                ),
                patch.object(
                    MemoryAPI,
                    "_update_weight_on_successful_use",
                    new_callable=AsyncMock,
                ),
            ):
                response = await MemoryAPI.add_semantic_fact(
                    tenant_id=TEST_TENANT_ID,
                    entity_type=TEST_ENTITY_TYPE,
                    entity_id=TEST_ENTITY_ID,
                    attributes={"name": "John"},
                    session_id=TEST_SESSION_ID,
                    # No source metadata provided
                )

            # Should still return a valid FactResponse
            assert response.entity_id == TEST_ENTITY_ID
            assert response.source_agent_id is None
            assert response.source_query_id is None
            assert response.source_confidence_score == 1.0


class TestPhase5BFactResponseModel:
    """Test suite for extended FactResponse model."""

    def test_fact_response_includes_all_phase5b_fields(self) -> None:
        """FactResponse should include all Phase 5B fields."""
        response = FactResponse(
            tenant_id=TEST_TENANT_ID,
            entity_id=TEST_ENTITY_ID,
            entity_type=TEST_ENTITY_TYPE,
            node_path="/PERSON/ent_123",
            weight=DEFAULT_WEIGHT,
            created_at=datetime.now(UTC),
            source_confidence_score=TEST_CONFIDENCE_SCORE,
            detected_contradictions=[{"severity": "high", "conflicting_nodes": []}],
            source_agent_id=TEST_AGENT_ID,
            source_query_id=TEST_QUERY_ID,
        )

        assert response.source_confidence_score == TEST_CONFIDENCE_SCORE
        assert len(response.detected_contradictions) == 1
        assert response.source_agent_id == TEST_AGENT_ID
        assert response.source_query_id == TEST_QUERY_ID

    def test_fact_response_phase5b_fields_optional(self) -> None:
        """Phase 5B fields should be optional (backward compatible)."""
        response = FactResponse(
            tenant_id=TEST_TENANT_ID,
            entity_id=TEST_ENTITY_ID,
            entity_type=TEST_ENTITY_TYPE,
            node_path="/PERSON/ent_123",
            weight=DEFAULT_WEIGHT,
            created_at=datetime.now(UTC),
        )

        assert response.source_confidence_score == DEFAULT_CONFIDENCE_SCORE
        assert response.detected_contradictions == []  # Default
        assert response.source_agent_id is None  # Default
        assert response.source_query_id is None  # Default
