"""Unit tests for memory session lifecycle and semantic fact writes."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.schema import SchemaConfig
from src.memory.api import MemoryAPI
from src.models.schemas import FactResponse, SessionResponse


class TestMemoryApiSessionsAndFacts:
    """Behavioral tests for session creation and fact persistence."""

    async def test_create_session_includes_tenant_on_node_and_response(self) -> None:
        """Session creation should persist and return the tenant identifier."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            response = await MemoryAPI.create_session(
                tenant_id="tenant_a",
                session_id="session_123",
                user_id="user_456",
            )

        assert isinstance(response, SessionResponse)
        assert response.tenant_id == "tenant_a"
        assert response.session_id == "session_123"
        node_params = mock_batch.execute_update.call_args_list[0].args[1]
        audit_params = mock_batch.execute_update.call_args_list[1].args[1]
        assert node_params["tenant_id"] == "tenant_a"
        assert node_params["action_count"] == 0
        assert audit_params["tenant_id"] == "tenant_a"
        assert json.loads(node_params["attributes"])["user_id"] == "user_456"

    async def test_create_session_rejects_blank_tenant(self) -> None:
        """Session creation should fail fast on blank tenant identifiers."""
        with pytest.raises(ValueError, match="tenant_id cannot be blank"):
            await MemoryAPI.create_session(
                tenant_id="   ",
                session_id="session_123",
                user_id="user_456",
            )

    async def test_add_semantic_fact_includes_tenant_everywhere(self) -> None:
        """Semantic fact creation should scope node, edge, and audit writes to one tenant."""
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
            mock_client.validate_tenant_id.return_value = "tenant_a"

            with (
                patch.object(
                    MemoryAPI,
                    "_increment_session_action_count",
                    return_value=4,
                ) as mock_increment,
                patch.object(
                    MemoryAPI,
                    "_update_weight_on_successful_use",
                    new_callable=AsyncMock,
                ) as mock_update,
            ):
                response = await MemoryAPI.add_semantic_fact(
                    tenant_id="tenant_a",
                    entity_type="PERSON",
                    entity_id="entity_123",
                    attributes={"name": "John"},
                    relationship={"source_id": "source_123", "type": "REFERENCES"},
                    session_id="session_123",
                )

        assert isinstance(response, FactResponse)
        assert response.tenant_id == "tenant_a"
        node_params = mock_batch.execute_update.call_args_list[0].args[1]
        edge_params = mock_batch.execute_update.call_args_list[1].args[1]
        audit_params = mock_batch.execute_update.call_args_list[2].args[1]
        assert node_params["tenant_id"] == "tenant_a"
        assert edge_params["tenant_id"] == "tenant_a"
        assert audit_params["tenant_id"] == "tenant_a"
        mock_increment.assert_called_once_with("tenant_a", "session_123")
        mock_update.assert_awaited_once_with(
            "tenant_a",
            ["entity_123"],
            session_action_count=4,
        )

    async def test_add_semantic_fact_rejects_cross_tenant_relationship_source(self) -> None:
        """Relationship creation should fail when the source node is absent in the tenant."""
        with (
            patch.object(MemoryAPI, "_get_node_memory_tier", return_value=None),
            pytest.raises(ValueError, match="not found in tenant"),
        ):
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_a",
                entity_type="PERSON",
                entity_id="entity_123",
                relationship={"source_id": "source_123", "type": "REFERENCES"},
            )

    async def test_record_audit_event_returns_tenant_scoped_response(self) -> None:
        """Explicit audit writes should return the tenant identifier in the response."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            response = await MemoryAPI.record_audit_event(
                tenant_id="tenant_a",
                event_type="CREATE_SESSION",
                source_node_id="session_123",
            )

        assert response.tenant_id == "tenant_a"
        call_params = mock_batch.execute_update.call_args.args[1]
        assert call_params["tenant_id"] == "tenant_a"
        assert call_params["event_type"] == "CREATE_SESSION"
