"""Unit tests for tenant validation in the Spanner client."""

from __future__ import annotations

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
