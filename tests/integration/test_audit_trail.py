"""Integration tests for memory API tripartite memory isolation."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.db.schema import SchemaConfig
from src.memory.api import MemoryAPI
from src.models.schemas import AuditResponse, ContextResponse, FactResponse, SessionResponse


class TestAuditTrail:
    """Integration tests for audit trail immutability and operation tracing."""

    @pytest.mark.asyncio
    async def test_session_creation_generates_audit_event(self):
        """Test that creating a session generates corresponding audit event."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            await MemoryAPI.create_session(session_id="session_123", user_id="user_456")

            assert mock_batch.execute_update.call_count == 2
            audit_params = mock_batch.execute_update.call_args_list[1][0][1]
            audit_attributes = json.loads(audit_params["attributes"])
            assert audit_attributes["event_type"] == "CREATE_SESSION"
            assert audit_attributes["source_node_id"] == "session_123"

    @pytest.mark.asyncio
    async def test_semantic_fact_addition_generates_audit(self):
        """Test that adding semantic fact generates audit event."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            with patch.object(MemoryAPI, "_update_weight_on_successful_use") as mock_weight:

                async def async_weight(*args, **kwargs):
                    pass

                mock_weight.side_effect = async_weight

                await MemoryAPI.add_semantic_fact(entity_type="PERSON", entity_id="entity_123")

                # Verify audit persisted and weight update was called
                audit_params = mock_batch.execute_update.call_args_list[1][0][1]
                audit_attributes = json.loads(audit_params["attributes"])
                assert audit_attributes["event_type"] == "ADD_SEMANTIC_FACT"
                assert audit_attributes["source_node_id"] == "entity_123"
                mock_weight.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_retrieval_updates_weights(self):
        """Test that retrieving context updates access weights (confirmation bias)."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_snapshot = MagicMock()
            mock_snapshot.execute_sql.return_value = [
                (
                    "turn_1",
                    "User",
                    '{"content": "Hello"}',
                    0.5,
                    datetime.now(UTC),
                    "HAS_TURN",
                ),
            ]
            mock_db.snapshot.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.snapshot.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            with (
                patch.object(MemoryAPI, "record_audit_event") as mock_audit,
                patch.object(MemoryAPI, "_update_weight_on_successful_use") as mock_weight,
            ):

                async def async_audit(*args, **kwargs):
                    return AuditResponse(
                        event_id="audit_3",
                        event_type=args[0],
                        timestamp=datetime.now(UTC),
                    )

                async def async_weight(*args, **kwargs):
                    pass

                mock_audit.side_effect = async_audit
                mock_weight.side_effect = async_weight

                response = await MemoryAPI.retrieve_context_window(session_id="session_123")

                # Verify weight update was called for retrieved turns
                mock_weight.assert_called_once_with(
                    ["turn_1"], memory_tier=SchemaConfig.MEMORY_TIER_CONTEXT
                )

    @pytest.mark.asyncio
    async def test_tripartite_memory_isolation(self):
        """Test that context, semantic, and audit memories remain isolated."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            with patch.object(
                MemoryAPI, "record_audit_event", new_callable=MagicMock
            ) as mock_audit:

                async def async_audit(*args, **kwargs):
                    return AuditResponse(
                        event_id="audit_4",
                        event_type=args[0],
                        timestamp=datetime.now(UTC),
                    )

                mock_audit.side_effect = async_audit

                # Create session (CONTEXT tier)
                session = await MemoryAPI.create_session(
                    session_id="session_456", user_id="user_789"
                )

                # Add semantic fact (SEMANTIC tier)
                with patch.object(MemoryAPI, "_update_weight_on_successful_use") as mock_weight:

                    async def async_weight(*args, **kwargs):
                        pass

                    mock_weight.side_effect = async_weight
                    fact = await MemoryAPI.add_semantic_fact(
                        entity_type="OBJECT", entity_id="object_123"
                    )

                # Verify each operation creates nodes in correct tier
                # Session should be in CONTEXT tier
                # Semantic fact should be in SEMANTIC tier
                # Audit events should be in AUDIT tier

                calls = mock_batch.execute_update.call_args_list
                # Should have: 1 session node + 1 fact node (audit is mocked out)
                assert len(calls) >= 2

                # Verify the memory tiers used in calls
                tiers_used = []
                for call in calls:
                    # call is a call object with args and kwargs
                    # call[0] is the positional args tuple
                    # call[1] is the keyword args dict
                    if len(call[0]) > 1:  # SQL and params
                        params = call[0][1]
                        if "tier" in params:
                            tiers_used.append(params["tier"])

                # At minimum, we should have CONTEXT and SEMANTIC tiers
                assert len(tiers_used) >= 2
                assert SchemaConfig.MEMORY_TIER_CONTEXT in tiers_used
                assert SchemaConfig.MEMORY_TIER_SEMANTIC in tiers_used


class TestCognitiveWeighting:
    """Tests for cognitive weight management and Bayesian updates."""

    @pytest.mark.asyncio
    async def test_initial_weight_baseline(self):
        """Test that new entities start with INITIAL_WEIGHT."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            with (
                patch.object(MemoryAPI, "record_audit_event"),
                patch.object(MemoryAPI, "_update_weight_on_successful_use"),
            ):

                async def async_noop(*args, **kwargs):
                    pass

                response = await MemoryAPI.add_semantic_fact(
                    entity_type="EVENT", entity_id="event_123"
                )

                assert response.weight == SchemaConfig.INITIAL_WEIGHT

    @pytest.mark.asyncio
    async def test_weight_update_uses_bayes_factor(self):
        """Test that weight updates use BAYES_FACTOR_SUCCESS."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            await MemoryAPI._update_weight_on_successful_use(["node_1"])

            # Verify the update SQL includes ln(BAYES_FACTOR_SUCCESS)
            call_args = mock_batch.execute_update.call_args
            assert call_args is not None

            # call_args is a tuple: (args, kwargs)
            # The SQL is in call_args[0][0] and the params are in call_args[0][1]
            params = call_args[0][1]
            delta = params.get("delta")

            import math

            expected_delta = math.log(SchemaConfig.BAYES_FACTOR_SUCCESS)
            assert delta == pytest.approx(expected_delta, abs=0.001)

    @pytest.mark.asyncio
    async def test_last_accessed_timestamp_updated(self):
        """Test that LastAccessed is updated on weight change."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            await MemoryAPI._update_weight_on_successful_use(["node_1"])

            # Verify SQL includes LastAccessed update
            call_args = mock_batch.execute_update.call_args
            sql = call_args[0][0]
            assert "LastAccessed" in sql
            assert "CURRENT_TIMESTAMP()" in sql
