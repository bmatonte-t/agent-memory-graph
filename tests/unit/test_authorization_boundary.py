"""Tests for phase-0 authorization boundary enforcement."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib import import_module
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp.service import MCPToolService
from src.memory.api import MemoryAPI
from src.models.mcp import MCPInvokeRequest, MCPToolName
from src.models.mindmap import MindMapResponse, MindMapTrace, StageTiming, SynthesisResult
from src.security.governance import AuthorizationPolicy, AuthorizationScope, GovernanceSettings


class TestAuthorizationBoundary:
    """Tests for deny-by-default authorization behavior."""

    def test_authorize_operation_denies_without_scope_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing scopes should be denied and logged when auth is enabled."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            authorization=AuthorizationPolicy(enabled=True, default_deny=True)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            with pytest.raises(PermissionError, match="authorization denied"):
                MemoryAPI._authorize_operation(
                    operation="retrieve_context_window",
                    tenant_id="tenant_a",
                    authorization_scope=None,
                    node_id="session_1",
                    label="Session",
                    memory_tier="CONTEXT",
                )

        call_params = mock_batch.execute_update.call_args.args[1]
        assert call_params["event_type"] == "AUTHZ_DENY"
        assert call_params["tenant_id"] == "tenant_a"

    async def test_memory_api_allows_semantic_fact_with_matching_scope(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A matching scope should allow a semantic write and log AUTHZ_ALLOW."""
        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            authorization=AuthorizationPolicy(enabled=True, default_deny=True)
        )
        monkeypatch.setattr("src.memory.api.settings", mock_settings)

        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_123"],
            allowed_labels=["PERSON"],
            allowed_memory_tiers=["SEMANTIC"],
        )

        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()
            mock_db.batch.return_value.__enter__.return_value = mock_batch
            mock_db.batch.return_value.__exit__.return_value = None
            mock_db.snapshot.return_value.__enter__.return_value = mock_snapshot
            mock_db.snapshot.return_value.__exit__.return_value = None
            mock_snapshot.execute_sql.return_value = [("SEMANTIC",)]
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            with patch.object(
                MemoryAPI,
                "_update_weight_on_successful_use",
                new_callable=AsyncMock,
            ) as mock_update:
                response = await MemoryAPI.add_semantic_fact(
                    tenant_id="tenant_a",
                    entity_type="PERSON",
                    entity_id="entity_123",
                    session_id="session_1",
                    session_action_count=3,
                    authorization_scope=scope,
                )

        assert response.entity_id == "entity_123"
        auth_params = mock_batch.execute_update.call_args_list[0].args[1]
        assert auth_params["event_type"] == "AUTHZ_ALLOW"
        mock_update.assert_awaited_once_with(
            "tenant_a",
            ["entity_123"],
            session_action_count=3,
        )

    async def test_mcp_service_denies_without_scope_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """MCP should return a stable permission error when the scope is missing."""
        settings_module = import_module("src.project_base.settings")

        mock_settings = MagicMock()
        mock_settings.governance = GovernanceSettings(
            authorization=AuthorizationPolicy(enabled=True, default_deny=True)
        )
        monkeypatch.setattr(settings_module, "settings", mock_settings)

        fake_pipeline = AsyncMock()
        fake_pipeline.execute.return_value = MindMapResponse(
            query="test",
            synthesis=SynthesisResult(
                response_text="ok",
                claim_fact_ids=[],
                grounded=True,
                latency_ms=1.0,
            ),
            trace=MindMapTrace(
                trace_id="trace_1",
                mined_entities=[],
                path_ids=[],
                fact_ids=[],
                stage_timings=[StageTiming(stage="mine", latency_ms=1.0)],
                created_at=datetime.now(UTC),
            ),
        )
        service = MCPToolService(mindmap_pipeline=fake_pipeline)

        response = await service.invoke(
            MCPInvokeRequest(
                tenant_id="tenant_a",
                session_id="session_1",
                tool_name=MCPToolName.MEMORY_SEARCH,
                arguments={"query": "test", "session_id": "session_1"},
            )
        )

        assert response.success is False
        assert response.error is not None
        assert response.error.code == "permission_denied"
