"""Integration tests for Phase 3 ABAC authorization enforcement.

This module tests comprehensive ABAC scenarios including:
- Denied agent access to unauthorized resources
- Multi-tenant isolation with ABAC
- Authorization audit trail completeness
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

import src.memory.api as memory_api
from src.memory.api import MemoryAPI
from src.security.governance import AuthorizationPolicy, AuthorizationScope, GovernanceSettings


@dataclass(slots=True)
class _BatchStub:
    """Batch stub that records update statements for audit assertions."""

    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def execute_update(self, sql: str, params: dict[str, object]) -> int:
        """Record write operations and return success.

        Args:
            sql: SQL statement string.
            params: SQL parameters.

        Returns:
            int: Number of affected rows.
        """
        self.calls.append((sql, params))
        return 1


class _BatchContext:
    """Context manager for the batch stub."""

    def __init__(self, batch: _BatchStub) -> None:
        """Initialize wrapper.

        Args:
            batch: Batch stub.
        """
        self._batch = batch

    def __enter__(self) -> _BatchStub:
        """Return the batch stub.

        Returns:
            _BatchStub: Writable batch object.
        """
        return self._batch

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        """Do not suppress exceptions.

        Returns:
            bool: Always False.
        """
        del exc_type, exc_value, traceback
        return False


@dataclass(slots=True)
class _DatabaseStub:
    """Database stub exposing only interfaces used by authorization paths."""

    batch_stub: _BatchStub = field(default_factory=_BatchStub)

    def batch(self) -> _BatchContext:
        """Return writable batch context.

        Returns:
            _BatchContext: Context manager for batch writes.
        """
        return _BatchContext(self.batch_stub)

    def run_in_transaction(self, operation: object) -> object:
        """Execute transaction callback against the same batch stub.

        Args:
            operation: Transaction callback callable.

        Returns:
            object: Callback result.
        """
        if not callable(operation):
            msg = "operation must be callable"
            raise TypeError(msg)
        return operation(self.batch_stub)


class _SpannerClientStub:
    """Spanner client stub for ABAC authorization tests."""

    _database = _DatabaseStub()

    @staticmethod
    def get_database() -> _DatabaseStub:
        """Return shared in-memory database.

        Returns:
            _DatabaseStub: In-memory database stub.
        """
        return _SpannerClientStub._database

    @staticmethod
    def validate_tenant_id(tenant_id: str) -> str:
        """Return validated tenant identifier.

        Args:
            tenant_id: Incoming tenant identifier.

        Returns:
            str: Same tenant identifier.
        """
        return tenant_id

    @staticmethod
    def _validate_audit_mutation_forbidden(table_name: str, operation: str) -> None:
        """Allow append-only audit writes in integration tests.

        Args:
            table_name: Audit table name.
            operation: Requested mutation operation.
        """
        del table_name, operation


class TestABACDeniedAccess:
    """Tests for denied agent access scenarios."""

    @pytest.fixture(autouse=True)
    def _configure_authorization(self) -> object:
        """Enable strict ABAC policy and inject deterministic Spanner client."""
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

    async def test_denied_agent_cannot_add_semantic_fact(
        self,
    ) -> None:
        """Agent without allowed_node_ids cannot add facts to protected nodes."""
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["allowed_entity_1", "allowed_entity_2"],
            allowed_labels=["PERSON"],
            allowed_memory_tiers=["SEMANTIC"],
        )

        with pytest.raises(PermissionError, match="authorization denied"):
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_a",
                entity_type="PERSON",
                entity_id="denied_entity",
                authorization_scope=scope,
            )

    async def test_denied_agent_cannot_read_context_outside_scope(
        self,
    ) -> None:
        """Agent cannot retrieve context for unauthorized session."""
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["allowed_session_1"],
            allowed_labels=["Session"],
            allowed_memory_tiers=["CONTEXT"],
        )

        with pytest.raises(PermissionError, match="authorization denied"):
            await MemoryAPI.retrieve_context_window(
                tenant_id="tenant_a",
                session_id="denied_session",
                authorization_scope=scope,
            )

    async def test_empty_scope_denies_all_operations(
        self,
    ) -> None:
        """Empty scope with no configured dimensions denies all access."""
        # Empty allowed lists = no dimensions configured = denies all
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=[],
            allowed_labels=[],
            allowed_memory_tiers=[],
            allowed_relationship_types=[],
        )

        with pytest.raises(PermissionError, match="authorization denied"):
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_a",
                entity_type="PERSON",
                entity_id="entity_1",
                authorization_scope=scope,
            )


class TestABACLabelEnforcement:
    """Tests for ABAC enforcement on entity labels."""

    @pytest.fixture(autouse=True)
    def _configure_authorization(self) -> object:
        """Enable strict ABAC policy and inject deterministic Spanner client."""
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

    async def test_agent_cannot_create_unauthorized_label(
        self,
    ) -> None:
        """Agent with restricted labels cannot create other label types."""
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1"],
            allowed_labels=["PERSON"],
            allowed_memory_tiers=["SEMANTIC"],
        )

        with pytest.raises(PermissionError, match="authorization denied"):
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_a",
                entity_type="OBJECT",
                entity_id="entity_1",
                authorization_scope=scope,
            )


class TestABACMemoryTierEnforcement:
    """Tests for ABAC enforcement on memory tier access."""

    @pytest.fixture(autouse=True)
    def _configure_authorization(self) -> object:
        """Enable strict ABAC policy and inject deterministic Spanner client."""
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

    async def test_agent_cannot_access_unauthorized_memory_tier(
        self,
    ) -> None:
        """Agent restricted to CONTEXT tier cannot access SEMANTIC."""
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1"],
            allowed_labels=["PERSON"],
            allowed_memory_tiers=["CONTEXT"],
        )

        with pytest.raises(PermissionError, match="authorization denied"):
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_a",
                entity_type="PERSON",
                entity_id="entity_1",
                authorization_scope=scope,
            )


class TestABACAuthorizationAuditTrail:
    """Tests for authorization decision audit logging."""

    @pytest.fixture(autouse=True)
    def _configure_authorization(self) -> object:
        """Enable strict ABAC policy and inject deterministic Spanner client."""
        _SpannerClientStub._database = _DatabaseStub()
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

    def test_denied_decision_is_recorded(
        self,
    ) -> None:
        """Authorization denials are recorded in audit trail."""
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1"],
            allowed_labels=["PERSON"],
            allowed_memory_tiers=["SEMANTIC"],
        )

        with pytest.raises(PermissionError):
            MemoryAPI._authorize_operation(
                operation="test_operation",
                tenant_id="tenant_a",
                authorization_scope=scope,
                node_id="denied_entity",
                label="PERSON",
                memory_tier="SEMANTIC",
            )

        calls = _SpannerClientStub.get_database().batch_stub.calls
        assert len(calls) > 0
