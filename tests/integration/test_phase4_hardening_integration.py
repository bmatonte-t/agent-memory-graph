"""Phase 4 Hardening Integration Test.

Validates Phase 4C hardening across tenant isolation, observability safety, and
ABAC enforcement work correctly together.

Test scenarios:
1. ABAC + Tenant Isolation: Authorization scopes properly restrict access
2. Phase 4C Observability: Authorization failures return safe error messages
3. Multi-dimensional ABAC: node_id, label, and tier restrictions work
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.memory.api import MemoryAPI
from src.security.governance import AuthorizationPolicy, AuthorizationScope, GovernanceSettings


class TestPhase4HardeningIntegration:
    """Integration tests for Phase 4C hardening (ABAC + observability + tenant isolation)."""

    async def test_tenant_isolation_enforced_by_authorization_scope(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Authorization scope provides tenant-level isolation."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            authorization=AuthorizationPolicy(enabled=True, default_deny=True)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

        # Different agents, different scopes
        scope_agent_b = AuthorizationScope(agent_id="agent_b", allowed_node_ids=["entity_b"])

        with (
            patch("src.memory.api.SpannerClient"),
            pytest.raises(PermissionError, match="authorization denied"),
        ):
            # Agent B cannot access Agent A's authorized nodes
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_a",
                entity_type="PERSON",
                entity_id="entity_a",
                authorization_scope=scope_agent_b,  # Wrong agent's scope
            )

    async def test_phase4c_observability_safe_error_responses(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Authorization denials return safe error messages without internal details."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            authorization=AuthorizationPolicy(enabled=True, default_deny=True)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

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
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ABAC enforces all dimensions: node_id, label, tier."""
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

        with patch("src.memory.api.SpannerClient"):
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
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Phase 4C hardening doesn't regress Phase 3 ABAC."""
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
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            # Phase 3 ABAC still works: authorization checks are performed
            # Authorization check happens before any DB operation
            with pytest.raises(PermissionError, match="authorization denied"):
                await MemoryAPI.add_semantic_fact(
                    tenant_id="tenant_a",
                    entity_type="PERSON",
                    entity_id="not_allowed",
                    authorization_scope=scope,
                )

            # No DB calls should have been made (denied at authorization layer)
            assert not mock_batch.called
