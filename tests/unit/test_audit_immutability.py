"""Unit tests for audit immutability controls across schema client and memory API."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.db.spanner_client import SpannerClient
from src.memory.api import MemoryAPI


class TestAuditImmutability:
    """Audit immutability behavior should remain append-only by design."""

    def test_execute_update_rejects_update_on_audit_events(self) -> None:
        """Low-level DML should block UPDATE attempts for audit events."""
        with patch("src.db.spanner_client.SpannerClient.get_database") as mock_get_database:
            mock_database = MagicMock()
            mock_batch = MagicMock()
            mock_database.batch.return_value.__enter__.return_value = mock_batch
            mock_database.batch.return_value.__exit__.return_value = None
            mock_get_database.return_value = mock_database

            with pytest.raises(PermissionError, match="forbidden"):
                SpannerClient.execute_update(
                    "UPDATE AUDIT_EVENTS SET EventType = @event_type WHERE EventId = @event_id",
                    {"event_type": "UPDATED", "event_id": "evt_1"},
                )

        mock_batch.execute_update.assert_not_called()

    def test_execute_update_rejects_delete_on_audit_events(self) -> None:
        """Low-level DML should block DELETE attempts for audit events."""
        with patch("src.db.spanner_client.SpannerClient.get_database") as mock_get_database:
            mock_database = MagicMock()
            mock_batch = MagicMock()
            mock_database.batch.return_value.__enter__.return_value = mock_batch
            mock_database.batch.return_value.__exit__.return_value = None
            mock_get_database.return_value = mock_database

            with pytest.raises(PermissionError, match="forbidden"):
                SpannerClient.execute_update(
                    "DELETE FROM AUDIT_EVENTS WHERE EventId = @event_id",
                    {"event_id": "evt_1"},
                )

        mock_batch.execute_update.assert_not_called()

    def test_execute_update_allows_insert_on_audit_events(self) -> None:
        """Low-level DML should allow INSERT operations for append-only audit writes."""
        with patch("src.db.spanner_client.SpannerClient.get_database") as mock_get_database:
            mock_database = MagicMock()
            mock_batch = MagicMock()
            mock_database.batch.return_value.__enter__.return_value = mock_batch
            mock_database.batch.return_value.__exit__.return_value = None
            mock_batch.execute_update.return_value = 1
            mock_get_database.return_value = mock_database

            row_count = SpannerClient.execute_update(
                "INSERT INTO AUDIT_EVENTS (EventId, TenantId, SourceNodeId, EventType, CreatedAt) "
                "VALUES (@event_id, @tenant_id, @source_node_id, @event_type, @created_at)",
                {
                    "event_id": "evt_1",
                    "tenant_id": "tenant_a",
                    "source_node_id": "node_1",
                    "event_type": "CREATE_SESSION",
                    "created_at": datetime.now(UTC),
                },
            )

        assert row_count == 1
        mock_batch.execute_update.assert_called_once()

    def test_insert_audit_event_uses_append_only_guard(self) -> None:
        """Memory API audit writes should pass through append-only guard checks."""
        mock_batch = MagicMock()
        with patch.object(
            MemoryAPI,
            "_enforce_audit_append_only",
        ) as mock_guard:
            response = MemoryAPI._insert_audit_event_in_batch(
                batch=mock_batch,
                tenant_id="tenant_a",
                event_type="CREATE_SESSION",
                source_node_id="session_1",
                context={"request_id": "req_1"},
                timestamp=datetime.now(UTC),
            )

        mock_guard.assert_called_once_with("INSERT")
        assert response.tenant_id == "tenant_a"

    async def test_update_weight_rejects_audit_tier(self) -> None:
        """Updating audit tier weights should keep append-only behavior immutable."""
        with patch.object(
            MemoryAPI,
            "_enforce_audit_append_only",
        ) as mock_guard:
            with pytest.raises(ValueError, match="append-only"):
                await MemoryAPI._update_weight_on_successful_use(
                    tenant_id="tenant_a",
                    node_ids=["audit_node_1"],
                    memory_tier="AUDIT",
                )
        mock_guard.assert_called_once_with("UPDATE")
