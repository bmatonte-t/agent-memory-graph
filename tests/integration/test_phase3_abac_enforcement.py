"""Integration tests for Phase 3 ABAC authorization enforcement.

This module tests comprehensive ABAC scenarios including:
- Denied agent access to unauthorized resources
- Multi-tenant isolation with ABAC
- Authorization audit trail completeness
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.memory.api import MemoryAPI
from src.security.governance import AuthorizationPolicy, AuthorizationScope, GovernanceSettings


class TestABACDeniedAccess:
    """Tests for denied agent access scenarios."""

    async def test_denied_agent_cannot_add_semantic_fact(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Agent without allowed_node_ids cannot add facts to protected nodes."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            authorization=AuthorizationPolicy(enabled=True, default_deny=True)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["allowed_entity_1", "allowed_entity_2"],
            allowed_labels=["PERSON"],
            allowed_memory_tiers=["SEMANTIC"],
        )

        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            # Attempt to add fact for unauthorized node
            with pytest.raises(PermissionError, match="authorization denied"):
                await MemoryAPI.add_semantic_fact(
                    tenant_id="tenant_a",
                    entity_type="PERSON",
                    entity_id="denied_entity",
                    authorization_scope=scope,
                )

    async def test_denied_agent_cannot_read_context_outside_scope(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Agent cannot retrieve context for unauthorized session."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            authorization=AuthorizationPolicy(enabled=True, default_deny=True)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["allowed_session_1"],
            allowed_labels=["Session"],
            allowed_memory_tiers=["CONTEXT"],
        )

        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            # Attempt to read context for denied session
            with pytest.raises(PermissionError, match="authorization denied"):
                await MemoryAPI.retrieve_context_window(
                    tenant_id="tenant_a",
                    session_id="denied_session",
                    authorization_scope=scope,
                )

    async def test_empty_scope_denies_all_operations(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Empty scope with no configured dimensions denies all access."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            authorization=AuthorizationPolicy(enabled=True, default_deny=True)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

        # Empty allowed lists = no dimensions configured = denies all
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=[],
            allowed_labels=[],
            allowed_memory_tiers=[],
            allowed_relationship_types=[],
        )

        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            # All operations should be denied with empty scope
            with pytest.raises(PermissionError, match="authorization denied"):
                await MemoryAPI.add_semantic_fact(
                    tenant_id="tenant_a",
                    entity_type="PERSON",
                    entity_id="entity_1",
                    authorization_scope=scope,
                )


class TestABACLabelEnforcement:
    """Tests for ABAC enforcement on entity labels."""

    async def test_agent_cannot_create_unauthorized_label(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Agent with restricted labels cannot create other label types."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            authorization=AuthorizationPolicy(enabled=True, default_deny=True)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1"],
            allowed_labels=["PERSON"],
            allowed_memory_tiers=["SEMANTIC"],
        )

        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            # Attempt to create OBJECT entity (outside allowed labels)
            with pytest.raises(PermissionError, match="authorization denied"):
                await MemoryAPI.add_semantic_fact(
                    tenant_id="tenant_a",
                    entity_type="OBJECT",
                    entity_id="entity_1",
                    authorization_scope=scope,
                )


class TestABACMemoryTierEnforcement:
    """Tests for ABAC enforcement on memory tier access."""

    async def test_agent_cannot_access_unauthorized_memory_tier(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Agent restricted to CONTEXT tier cannot access SEMANTIC."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            authorization=AuthorizationPolicy(enabled=True, default_deny=True)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1"],
            allowed_labels=["PERSON"],
            allowed_memory_tiers=["CONTEXT"],
        )

        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            # Attempt to add SEMANTIC fact (outside allowed tiers)
            with pytest.raises(PermissionError, match="authorization denied"):
                await MemoryAPI.add_semantic_fact(
                    tenant_id="tenant_a",
                    entity_type="PERSON",
                    entity_id="entity_1",
                    authorization_scope=scope,
                )


class TestABACAuthorizationAuditTrail:
    """Tests for authorization decision audit logging."""

    def test_denied_decision_is_recorded(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Authorization denials are recorded in audit trail."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            authorization=AuthorizationPolicy(enabled=True, default_deny=True)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1"],
            allowed_labels=["PERSON"],
            allowed_memory_tiers=["SEMANTIC"],
        )

        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            # Attempt denied operation
            with pytest.raises(PermissionError):
                MemoryAPI._authorize_operation(
                    operation="test_operation",
                    tenant_id="tenant_a",
                    authorization_scope=scope,
                    node_id="denied_entity",
                    label="PERSON",
                    memory_tier="SEMANTIC",
                )

            # Verify audit event was recorded
            calls = mock_batch.execute_update.call_args_list
            assert len(calls) > 0
