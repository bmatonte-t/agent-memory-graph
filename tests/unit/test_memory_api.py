"""Unit tests for core memory APIs."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.memory.api import MemoryAPI
from src.models.schemas import (
    AuditResponse,
    ContextResponse,
    ContextTurn,
    FactResponse,
    SessionResponse,
)


class TestMemoryAPI:
    """Unit tests for MemoryAPI."""

    @pytest.mark.asyncio
    async def test_create_session_success(self):
        """Test successful session creation."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            with patch.object(
                MemoryAPI, "record_audit_event", new_callable=AsyncMock
            ) as mock_audit:
                response = await MemoryAPI.create_session(
                    session_id="session_123", user_id="user_456"
                )

                assert isinstance(response, SessionResponse)
                assert response.session_id == "session_123"
                assert response.status == "active"
                assert isinstance(response.created_at, datetime)
                mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_empty_session_id(self):
        """Test session creation with empty session_id."""
        with pytest.raises(ValueError, match="session_id and user_id cannot be empty"):
            await MemoryAPI.create_session(session_id="", user_id="user_456")

    @pytest.mark.asyncio
    async def test_create_session_empty_user_id(self):
        """Test session creation with empty user_id."""
        with pytest.raises(ValueError, match="session_id and user_id cannot be empty"):
            await MemoryAPI.create_session(session_id="session_123", user_id="")

    @pytest.mark.asyncio
    async def test_add_semantic_fact_success(self):
        """Test successful semantic fact addition."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            with patch.object(
                MemoryAPI, "record_audit_event", new_callable=AsyncMock
            ), patch.object(
                MemoryAPI, "_update_weight_on_successful_use", new_callable=AsyncMock
            ):
                response = await MemoryAPI.add_semantic_fact(
                    entity_type="PERSON",
                    entity_id="entity_123",
                    attributes={"name": "John"},
                )

                assert isinstance(response, FactResponse)
                assert response.entity_id == "entity_123"
                assert response.entity_type == "PERSON"
                assert response.weight == 0.5

    @pytest.mark.asyncio
    async def test_add_semantic_fact_invalid_entity_type(self):
        """Test semantic fact with invalid entity type."""
        with pytest.raises(ValueError, match="Invalid entity_type"):
            await MemoryAPI.add_semantic_fact(
                entity_type="INVALID_TYPE", entity_id="entity_123"
            )

    @pytest.mark.asyncio
    async def test_add_semantic_fact_empty_entity_id(self):
        """Test semantic fact with empty entity_id."""
        with pytest.raises(ValueError, match="entity_id cannot be empty"):
            await MemoryAPI.add_semantic_fact(entity_type="PERSON", entity_id="")

    @pytest.mark.asyncio
    async def test_add_semantic_fact_with_relationship(self):
        """Test semantic fact creation with relationship."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            with patch.object(
                MemoryAPI, "record_audit_event", new_callable=AsyncMock
            ), patch.object(
                MemoryAPI, "_update_weight_on_successful_use", new_callable=AsyncMock
            ):
                relationship = {"source_id": "source_123", "type": "REFERENCES"}
                response = await MemoryAPI.add_semantic_fact(
                    entity_type="LOCATION",
                    entity_id="location_123",
                    relationship=relationship,
                )

                assert response.entity_id == "location_123"
                # Verify that execute_update was called twice (node + edge)
                assert mock_batch.execute_update.call_count == 2

    @pytest.mark.asyncio
    async def test_record_audit_event_success(self):
        """Test successful audit event recording."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            response = await MemoryAPI.record_audit_event(
                event_type="CREATE_SESSION", source_node_id="session_123"
            )

            assert isinstance(response, AuditResponse)
            assert response.event_type == "CREATE_SESSION"
            assert isinstance(response.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_record_audit_event_empty_event_type(self):
        """Test audit event with empty event_type."""
        with pytest.raises(
            ValueError, match="event_type and source_node_id cannot be empty"
        ):
            await MemoryAPI.record_audit_event(
                event_type="", source_node_id="source_123"
            )

    @pytest.mark.asyncio
    async def test_record_audit_event_empty_source_node_id(self):
        """Test audit event with empty source_node_id."""
        with pytest.raises(
            ValueError, match="event_type and source_node_id cannot be empty"
        ):
            await MemoryAPI.record_audit_event(
                event_type="CREATE_SESSION", source_node_id=""
            )

    @pytest.mark.asyncio
    async def test_retrieve_context_window_success(self):
        """Test successful context window retrieval."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_snapshot = MagicMock()
            mock_snapshot.execute_sql.return_value = [
                (
                    "turn_1",
                    "User",
                    '{"content": "Hello"}',
                    0.6,
                    datetime.utcnow(),
                    "HAS_TURN",
                ),
                (
                    "turn_2",
                    "Agent",
                    '{"content": "Hi"}',
                    0.55,
                    datetime.utcnow(),
                    "HAS_TURN",
                ),
            ]
            mock_db.snapshot.return_value.__enter__ = MagicMock(
                return_value=mock_snapshot
            )
            mock_db.snapshot.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            with patch.object(
                MemoryAPI, "record_audit_event", new_callable=AsyncMock
            ), patch.object(
                MemoryAPI, "_update_weight_on_successful_use", new_callable=AsyncMock
            ):
                response = await MemoryAPI.retrieve_context_window(
                    session_id="session_123", window_size=10
                )

                assert isinstance(response, ContextResponse)
                assert response.session_id == "session_123"
                assert len(response.turns) == 2
                assert response.total_weight_sum == pytest.approx(1.15, abs=0.01)

    @pytest.mark.asyncio
    async def test_retrieve_context_window_empty_session_id(self):
        """Test context retrieval with empty session_id."""
        with pytest.raises(ValueError, match="session_id cannot be empty"):
            await MemoryAPI.retrieve_context_window(session_id="")

    @pytest.mark.asyncio
    async def test_retrieve_context_window_invalid_window_size(self):
        """Test context retrieval with invalid window size."""
        with pytest.raises(ValueError, match="window_size must be between 1 and 100"):
            await MemoryAPI.retrieve_context_window(
                session_id="session_123", window_size=0
            )

        with pytest.raises(ValueError, match="window_size must be between 1 and 100"):
            await MemoryAPI.retrieve_context_window(
                session_id="session_123", window_size=101
            )

    @pytest.mark.asyncio
    async def test_update_weight_on_successful_use(self):
        """Test cognitive weight update."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            await MemoryAPI._update_weight_on_successful_use(
                ["node_1", "node_2"]
            )

            mock_batch.execute_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_weight_on_empty_node_ids(self):
        """Test weight update with empty node IDs (should return early)."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            await MemoryAPI._update_weight_on_successful_use([])
            mock_client.get_database.assert_not_called()
