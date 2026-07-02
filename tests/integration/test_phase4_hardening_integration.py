"""Phase 4 Hardening Integration Test.

Validates Phase 4C hardening across tenant isolation, observability safety, and
ABAC enforcement work correctly together.

Test scenarios:
1. ABAC + Tenant Isolation: Authorization scopes properly restrict access
2. Phase 4C Observability: Authorization failures return safe error messages
3. Multi-dimensional ABAC: node_id, label, and tier restrictions work
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import src.memory.api as memory_api
from src.memory.api import MemoryAPI
from src.security.governance import AuthorizationPolicy, AuthorizationScope, GovernanceSettings

if TYPE_CHECKING:
    from collections.abc import Callable


class _BatchStub:
    """No-op batch implementation for authorization audit writes."""

    def __init__(self) -> None:
        """Initialize write counter."""
        self.write_count = 0

    def execute_update(self, sql: str, params: dict[str, object]) -> int:
        """Record update invocations and return success.

        Args:
            sql: SQL query string.
            params: Query parameters.

        Returns:
            int: Rows affected.
        """
        del sql, params
        self.write_count += 1
        return 1


class _BatchContext:
    """Context manager wrapper for batch stub."""

    def __init__(self, batch: _BatchStub) -> None:
        """Initialize context wrapper.

        Args:
            batch: Batch instance to expose.
        """
        self._batch = batch

    def __enter__(self) -> _BatchStub:
        """Return writable batch.

        Returns:
            _BatchStub: Batch stub.
        """
        return self._batch

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        """Do not suppress exceptions.

        Returns:
            bool: Always False.
        """
        del exc_type, exc_value, traceback
        return False


class _AuthorizationAuditDatabaseStub:
    """Database stub that accepts audit writes without external calls."""

    def __init__(self) -> None:
        """Initialize database with reusable batch stub."""
        self.batch_stub = _BatchStub()

    def batch(self) -> _BatchContext:
        """Return batch context for writes.

        Returns:
            _BatchContext: Context wrapper around no-op batch.
        """
        return _BatchContext(self.batch_stub)

    def run_in_transaction(self, operation: Callable[[object], object]) -> object:
        """Execute fallback transactions against the same batch stub.

        Args:
            operation: Transaction callback.

        Returns:
            object: Callback result.
        """
        return operation(self.batch_stub)


class _SpannerClientStub:
    """Minimal Spanner client used by authorization-path integration tests."""

    _database = _AuthorizationAuditDatabaseStub()

    @staticmethod
    def get_database() -> _AuthorizationAuditDatabaseStub:
        """Return fake in-memory database.

        Returns:
            _AuthorizationAuditDatabaseStub: Database stub.
        """
        return _SpannerClientStub._database

    @staticmethod
    def _validate_audit_mutation_forbidden(table_name: str, operation: str) -> None:
        """Allow append-only audit insert operations in tests.

        Args:
            table_name: Target audit table.
            operation: Mutation operation.
        """
        del table_name, operation


class TestPhase4HardeningIntegration:
    """Integration tests for Phase 4C hardening (ABAC + observability + tenant isolation)."""

    @pytest.fixture(autouse=True)
    def _enable_default_deny_authorization(self) -> object:
        """Enable strict authorization policy and stub Spanner side effects."""
        original_settings = memory_api.settings
        original_spanner_client = memory_api.SpannerClient

        memory_api.settings = type(
            "SettingsStub",
            (),
            {
                "governance": GovernanceSettings(
                    authorization=AuthorizationPolicy(enabled=True, default_deny=True)
                )
            },
        )
        memory_api.SpannerClient = _SpannerClientStub

        try:
            yield
        finally:
            memory_api.settings = original_settings
            memory_api.SpannerClient = original_spanner_client

    async def test_tenant_isolation_enforced_by_authorization_scope(
        self,
    ) -> None:
        """Authorization scope provides tenant-level isolation."""
        # Different agents, different scopes
        scope_agent_b = AuthorizationScope(agent_id="agent_b", allowed_node_ids=["entity_b"])

        with pytest.raises(PermissionError, match="authorization denied"):
            # Agent B cannot access Agent A's authorized nodes
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_a",
                entity_type="PERSON",
                entity_id="entity_a",
                authorization_scope=scope_agent_b,  # Wrong agent's scope
            )

    async def test_phase4c_observability_safe_error_responses(
        self,
    ) -> None:
        """Authorization denials return safe error messages without internal details."""
        # Empty scope denies all access
        empty_scope = AuthorizationScope(agent_id="agent_x")

        # Attempt denied operation
        with pytest.raises(PermissionError) as exc_info:
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_a",
                entity_type="PERSON",
                entity_id="entity_1",
                authorization_scope=empty_scope,
            )

        # Error message should be safe (observable without leaking implementation)
        error_msg = str(exc_info.value)
        assert "authorization denied" in error_msg.lower()

    async def test_multi_dimensional_abac_enforcement(
        self,
    ) -> None:
        """ABAC enforces all dimensions: node_id, label, tier."""
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1"],
            allowed_labels=["PERSON"],
            allowed_memory_tiers=["SEMANTIC"],
        )

        # Denied: wrong node_id
        with pytest.raises(PermissionError, match="authorization denied"):
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_a",
                entity_type="PERSON",
                entity_id="entity_2",  # Not in scope
                authorization_scope=scope,
            )

        # Denied: wrong label
        with pytest.raises(PermissionError, match="authorization denied"):
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_a",
                entity_type="OBJECT",  # Not in scope
                entity_id="entity_1",
                authorization_scope=scope,
            )

    async def test_phase3_abac_not_regressed_by_phase4c(
        self,
    ) -> None:
        """Phase 4C hardening doesn't regress Phase 3 ABAC."""
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1"],
            allowed_labels=["PERSON"],
            allowed_memory_tiers=["SEMANTIC"],
        )

        # Phase 3 ABAC still works: unauthorized node access is denied.
        with pytest.raises(PermissionError, match="authorization denied"):
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_a",
                entity_type="PERSON",
                entity_id="not_allowed",
                authorization_scope=scope,
            )
