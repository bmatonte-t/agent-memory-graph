"""Unit tests for memory context retrieval and graph export behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from src.db.schema import SchemaConfig
from src.memory.api import MemoryAPI
from src.models.schemas import ContextResponse, GraphExportResponse

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

EXPECTED_SQL_FALLBACK_CALL_COUNT = 2
EXPECTED_PAGINATED_TURNS = 2
EXPECTED_PROCESSED_TURNS = 2


class TestMemoryApiContextAndGraph:
    """Behavioral tests for context window and graph snapshot APIs."""

    async def test_retrieve_context_window_returns_tenant_scoped_turns(
        self,
        context_turn_row_factory: Callable[..., tuple[str, str, str, float, datetime, str]],
    ) -> None:
        """Context retrieval should stamp each turn and the envelope with the tenant."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_snapshot = MagicMock()
            mock_db.snapshot.return_value.__enter__.return_value = mock_snapshot
            mock_db.snapshot.return_value.__exit__.return_value = None
            mock_snapshot.execute_sql.return_value = [
                context_turn_row_factory(
                    turn_id="turn_1",
                    role="User",
                    content="Hello",
                    weight=0.6,
                ),
                context_turn_row_factory(turn_id="turn_2", role="Agent", content="Hi", weight=0.55),
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
        assert response.has_more is False
        assert response.next_cursor is None
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

    async def test_retrieve_context_window_falls_back_when_match_unsupported(
        self,
        context_turn_row_factory: Callable[..., tuple[str, str, str, float, datetime, str]],
    ) -> None:
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
                            context_turn_row_factory(
                                turn_id="turn_1",
                                role="User",
                                content="Hello",
                                weight=0.6,
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

    async def test_retrieve_context_window_supports_cursor_pagination(
        self,
        context_turn_row_factory: Callable[..., tuple[str, str, str, float, datetime, str]],
    ) -> None:
        """Context retrieval should return next_cursor and has_more when additional turns exist."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_db.run_in_transaction.return_value = 1
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            rows = [
                context_turn_row_factory(turn_id="turn_3", role="User", content="3", weight=0.6),
                context_turn_row_factory(turn_id="turn_2", role="Agent", content="2", weight=0.55),
                context_turn_row_factory(turn_id="turn_1", role="User", content="1", weight=0.5),
            ]

            with (
                patch("src.memory.api.execute_sql_rows", return_value=rows),
                patch.object(MemoryAPI, "record_audit_event", new_callable=AsyncMock),
                patch.object(
                    MemoryAPI,
                    "_update_weight_on_successful_use",
                    new_callable=AsyncMock,
                ),
                patch.object(MemoryAPI, "_increment_session_action_count", return_value=1),
            ):
                response = await MemoryAPI.retrieve_context_window(
                    tenant_id="tenant_a",
                    session_id="session_123",
                    window_size=2,
                    cursor="2026-07-01T00:00:00+00:00|turn_99",
                )

        assert len(response.turns) == EXPECTED_PAGINATED_TURNS
        assert response.has_more is True
        assert response.next_cursor is not None

    async def test_export_graph_snapshot_returns_json_ld_entries(self) -> None:
        """Graph export should return tenant-scoped JSON-LD nodes and edges."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            node_rows = [
                ("node_1", "Session", "CONTEXT", 0.7, '{"status": "active"}'),
            ]
            edge_rows = [
                (
                    "edge_1",
                    "node_1",
                    "node_2",
                    "HAS_TURN",
                    0.4,
                    '{"source": "test"}',
                )
            ]

            with (
                patch(
                    "src.memory.api.execute_sql_rows",
                    side_effect=[node_rows, edge_rows],
                ),
                patch.object(MemoryAPI, "record_audit_event", new_callable=AsyncMock),
            ):
                response = await MemoryAPI.export_graph_snapshot(
                    tenant_id="tenant_a",
                    limit=100,
                )

        assert isinstance(response, GraphExportResponse)
        assert response.tenant_id == "tenant_a"
        assert response.node_count == 1
        assert response.edge_count == 1
        assert len(response.graph) == EXPECTED_PROCESSED_TURNS
