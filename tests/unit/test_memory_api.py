"""Unit tests for tenant-aware core memory APIs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.schema import SchemaConfig
from src.memory.api import MemoryAPI
from src.models.schemas import ContextResponse, FactResponse, SessionResponse
from src.security.governance import GovernanceSettings, WeightingTriggerPolicy

if TYPE_CHECKING:
    from collections.abc import Callable

EXPECTED_SQL_FALLBACK_CALL_COUNT = 2


class TestMemoryAPI:
    """Behavioral tests for tenant-aware memory operations."""

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

    async def test_retrieve_context_window_returns_tenant_scoped_turns(self) -> None:
        """Context retrieval should stamp each turn and the envelope with the tenant."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_snapshot = MagicMock()
            mock_db.snapshot.return_value.__enter__.return_value = mock_snapshot
            mock_db.snapshot.return_value.__exit__.return_value = None
            mock_snapshot.execute_sql.return_value = [
                ("turn_1", "User", '{"content": "Hello"}', 0.6, datetime.now(UTC), "HAS_TURN"),
                ("turn_2", "Agent", '{"content": "Hi"}', 0.55, datetime.now(UTC), "HAS_TURN"),
            ]
            mock_db.run_in_transaction.return_value = 2
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            with (
                patch.object(MemoryAPI, "record_audit_event", new_callable=AsyncMock) as mock_audit,
                patch.object(
                    MemoryAPI,
                    "_update_weight_on_successful_use",
                    new_callable=AsyncMock,
                ) as mock_update,
            ):
                response = await MemoryAPI.retrieve_context_window(
                    tenant_id="tenant_a",
                    session_id="session_123",
                    window_size=10,
                )

        assert isinstance(response, ContextResponse)
        assert response.tenant_id == "tenant_a"
        assert [turn.tenant_id for turn in response.turns] == ["tenant_a", "tenant_a"]
        mock_audit.assert_awaited_once_with(
            "tenant_a",
            "RETRIEVE_CONTEXT_WINDOW",
            "session_123",
            {"window_size": 10, "turns_retrieved": 2},
            authorization_scope=None,
        )
        mock_update.assert_awaited_once_with(
            "tenant_a",
            ["turn_1", "turn_2"],
            memory_tier=SchemaConfig.MEMORY_TIER_CONTEXT,
            session_action_count=2,
        )

    async def test_retrieve_context_window_falls_back_when_match_unsupported(self) -> None:
        """Context retrieval should use SQL fallback when graph MATCH is unavailable."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_db.run_in_transaction.return_value = 1
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            with (
                patch(
                    "src.memory.api.execute_sql_rows",
                    side_effect=[
                        RuntimeError("Unexpected keyword MATCH"),
                        [
                            (
                                "turn_1",
                                "User",
                                '{"content": "Hello"}',
                                0.6,
                                datetime.now(UTC),
                                "HAS_TURN",
                            )
                        ],
                    ],
                ) as mock_execute,
                patch.object(MemoryAPI, "record_audit_event", new_callable=AsyncMock) as mock_audit,
                patch.object(
                    MemoryAPI,
                    "_update_weight_on_successful_use",
                    new_callable=AsyncMock,
                ) as mock_update,
                patch.object(MemoryAPI, "_increment_session_action_count", return_value=1),
            ):
                response = await MemoryAPI.retrieve_context_window(
                    tenant_id="tenant_a",
                    session_id="session_123",
                    window_size=10,
                )

        assert response.tenant_id == "tenant_a"
        assert len(response.turns) == 1
        assert response.turns[0].turn_id == "turn_1"
        assert mock_execute.call_count == EXPECTED_SQL_FALLBACK_CALL_COUNT
        mock_audit.assert_awaited_once()
        mock_update.assert_awaited_once()

    async def test_update_weight_uses_tenant_filter(self) -> None:
        """Weight updates should include the tenant filter in DML parameters."""
        weighting_policy = WeightingTriggerPolicy(enabled=True, action_count_threshold=1)

        with (
            patch("src.memory.api.SpannerClient") as mock_client,
            patch("src.memory.api.settings.governance.weighting", weighting_policy),
        ):
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            await MemoryAPI._update_weight_on_successful_use(
                "tenant_a",
                ["node_1", "node_2"],
                memory_tier=SchemaConfig.MEMORY_TIER_CONTEXT,
                session_action_count=1,
            )

        params = mock_batch.execute_update.call_args.args[1]
        assert params["tenant_id"] == "tenant_a"
        assert params["tier"] == SchemaConfig.MEMORY_TIER_CONTEXT

    async def test_update_weight_rejects_audit_tier(self) -> None:
        """Append-only audit nodes must remain immutable even during weight updates."""
        with pytest.raises(ValueError, match="append-only"):
            await MemoryAPI._update_weight_on_successful_use(
                "tenant_a",
                ["node_1"],
                memory_tier=SchemaConfig.MEMORY_TIER_AUDIT,
            )

    async def test_increment_session_action_count_returns_next_value(self) -> None:
        """Session action counts should be persisted and incremented transactionally."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_transaction = MagicMock()
            mock_transaction.execute_sql.return_value = [(2,)]
            mock_db.run_in_transaction.return_value = 3
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            def _run_in_transaction(callback: Callable[[MagicMock], int]) -> int:
                return callback(mock_transaction)

            mock_db.run_in_transaction.side_effect = _run_in_transaction

            next_count = MemoryAPI._increment_session_action_count("tenant_a", "session_123")

        expected_next_count = 3
        assert next_count == expected_next_count
        mock_transaction.execute_update.assert_called_once()

    async def test_update_weight_skips_below_threshold_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Weighting should skip when an enabled trigger policy is not satisfied."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            weighting=WeightingTriggerPolicy(enabled=True, action_count_threshold=3)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            await MemoryAPI._update_weight_on_successful_use(
                "tenant_a",
                ["node_1"],
                memory_tier=SchemaConfig.MEMORY_TIER_SEMANTIC,
                session_action_count=2,
            )

        mock_batch.execute_update.assert_not_called()

    async def test_update_weight_runs_at_threshold_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Weighting should update once the configured action threshold is met."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            weighting=WeightingTriggerPolicy(enabled=True, action_count_threshold=3)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            await MemoryAPI._update_weight_on_successful_use(
                "tenant_a",
                ["node_1"],
                memory_tier=SchemaConfig.MEMORY_TIER_SEMANTIC,
                session_action_count=3,
            )

        mock_batch.execute_update.assert_called_once()
