"""Unit tests for tenant validation in the Spanner client."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.db.spanner_client import SpannerClient


class TestSpannerClient:
    """Tests for tenant-related Spanner client helpers."""

    def test_validate_tenant_id_strips_whitespace(self) -> None:
        """Tenant validation should normalize surrounding whitespace."""
        assert SpannerClient.validate_tenant_id(" tenant_a ") == "tenant_a"

    @pytest.mark.parametrize("tenant_id", [None, "", "   "])
    def test_validate_tenant_id_rejects_empty_values(self, tenant_id: str | None) -> None:
        """Tenant validation should reject missing and blank identifiers."""
        with pytest.raises(ValueError, match="tenant_id"):
            SpannerClient.validate_tenant_id(tenant_id)

    @pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
    def test_validate_audit_mutation_forbidden_rejects_mutations(self, operation: str) -> None:
        """Audit event rows should remain append-only for all mutation operations."""
        with pytest.raises(PermissionError, match="forbidden"):
            SpannerClient._validate_audit_mutation_forbidden("audit_events", operation)

    def test_validate_audit_mutation_forbidden_allows_insert(self) -> None:
        """Insert operations should remain allowed for audit event writes."""
        SpannerClient._validate_audit_mutation_forbidden("AUDIT_EVENTS", "INSERT")

    def test_validate_audit_mutation_forbidden_allows_other_tables(self) -> None:
        """Non-audit tables should not be blocked by the immutability helper."""
        SpannerClient._validate_audit_mutation_forbidden("MemoryNode", "UPDATE")

    def test_strip_leading_sql_comments_removes_comment_prefixes(self) -> None:
        """Leading SQL comments should be removed before policy inspection."""
        sql = """\
        -- comment one
        /* comment two */
        UPDATE AUDIT_EVENTS SET EventType = @event_type
        """

        assert SpannerClient._strip_leading_sql_comments(sql).startswith("UPDATE AUDIT_EVENTS")

    @pytest.mark.parametrize(
        ("sql", "_expected_operation"),
        [
            ("UPDATE AUDIT_EVENTS SET EventType = @event_type", "UPDATE"),
            ("WITH recent AS (SELECT 1) UPDATE AUDIT_EVENTS SET EventType = @event_type", "UPDATE"),
            ("/* comment */ DELETE FROM AUDIT_EVENTS WHERE EventId = @event_id", "DELETE"),
            (
                (
                    "-- comment\nMERGE INTO AUDIT_EVENTS USING source ON true "
                    "WHEN MATCHED THEN UPDATE SET EventType = 'x'"
                ),
                "MERGE",
            ),
            ("TRUNCATE TABLE AUDIT_EVENTS", "TRUNCATE"),
        ],
    )
    def test_validate_audit_table_mutation_blocks_wrapped_statements(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sql: str,
        _expected_operation: str,
    ) -> None:
        """Wrapped audit-table mutations should be rejected before execution."""
        mock_database = MagicMock()
        mock_batch = MagicMock()
        mock_database.batch.return_value.__enter__.return_value = mock_batch
        mock_database.batch.return_value.__exit__.return_value = None
        monkeypatch.setattr(
            "src.db.spanner_client.SpannerClient.get_database", lambda: mock_database
        )

        with pytest.raises(PermissionError, match="forbidden"):
            SpannerClient.execute_update(sql, {})

        mock_batch.execute_update.assert_not_called()
