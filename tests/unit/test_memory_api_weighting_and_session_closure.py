"""Unit tests for memory weighting policy and session closure workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.schema import SchemaConfig
from src.memory.api import MemoryAPI
from src.memory.exceptions import MemoryOperationError, WeightUpdateFailedError
from src.models.schemas import FactResponse, SessionKnowledgeExtractionResponse
from src.security.governance import GovernanceSettings, WeightingTriggerPolicy

if TYPE_CHECKING:
    from collections.abc import Callable

EXPECTED_PROCESSED_TURNS = 2
EXPECTED_AUDIT_EVENTS_FOR_EXTRACTION = 2
EXPECTED_EXTRACTED_FACTS = 2
EXPECTED_WEIGHT_UPDATE_ATTEMPTS = 3


class TestMemoryApiWeightingAndSessionClosure:
    """Behavioral tests for weighting updates and session finalization."""

    def test_weight_update_failure_preserves_diagnostic_context(self) -> None:
        """Retry exhaustion exposes the original error and affected tenant and nodes."""
        node_ids = ["node_1", "node_2"]
        last_error = RuntimeError("storage unavailable")
        error = WeightUpdateFailedError(
            tenant_id="tenant_a",
            node_ids=node_ids,
            attempts=EXPECTED_WEIGHT_UPDATE_ATTEMPTS,
            last_error=last_error,
        )

        assert isinstance(error, MemoryOperationError)
        assert error.tenant_id == "tenant_a"
        assert error.node_ids == node_ids
        assert error.attempts == EXPECTED_WEIGHT_UPDATE_ATTEMPTS
        assert error.last_error is last_error
        assert str(error) == (
            "Weight update failed after 3 attempts "
            "for tenant_id=tenant_a nodes=2: storage unavailable"
        )

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

    async def test_increment_session_action_count_returns_next_value(
        self,
    ) -> None:
        """Session action count uses one atomic UPDATE with no read-modify-write."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_transaction = MagicMock()
            mock_transaction.execute_update.return_value = 1
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = "tenant_a"

            def run_in_transaction(callback: Callable[[MagicMock], int]) -> int:
                """Run callback in a fake transaction context."""
                return callback(mock_transaction)

            mock_db.run_in_transaction.side_effect = run_in_transaction

            result = MemoryAPI._increment_session_action_count("tenant_a", "session_123")

        mock_transaction.execute_update.assert_called_once()
        assert "execute_sql_rows_in_transaction" not in str(mock_transaction.mock_calls)
        assert result == 1

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

    async def test_extract_session_knowledge_writes_semantic_facts(
        self,
        context_response_factory: Callable[..., object],
    ) -> None:
        """Extraction should create semantic facts from context turns and skip duplicates."""
        context_response = context_response_factory(
            tenant_id="tenant_a",
            session_id="session_123",
            turns=[
                ("turn_1", "User", "Necesito ayuda con el despliegue", 0.5),
                ("turn_2", "Agent", "Se resolvio con rollback", 0.5),
            ],
        )
        retrieved_at = datetime.now(UTC)

        with (
            patch.object(
                MemoryAPI,
                "retrieve_context_window",
                new=AsyncMock(return_value=context_response),
            ),
            patch.object(
                MemoryAPI,
                "_get_node_memory_tier",
                side_effect=[None, SchemaConfig.MEMORY_TIER_SEMANTIC],
            ),
            patch.object(
                MemoryAPI,
                "add_semantic_fact",
                new=AsyncMock(
                    return_value=FactResponse(
                        tenant_id="tenant_a",
                        entity_id="session_123:knowledge:turn_1",
                        entity_type="EVENT",
                        node_path="/EVENT/session_123:knowledge:turn_1",
                        weight=0.5,
                        created_at=retrieved_at,
                    )
                ),
            ) as mock_add_fact,
            patch.object(
                MemoryAPI,
                "record_audit_event",
                new=AsyncMock(),
            ) as mock_audit,
        ):
            response = await MemoryAPI.extract_session_knowledge(
                tenant_id="tenant_a",
                session_id="session_123",
                domain_hint="deployment",
                window_size=20,
            )

        assert response.tenant_id == "tenant_a"
        assert response.session_id == "session_123"
        assert response.domain == "deployment"
        assert response.processed_turns == EXPECTED_PROCESSED_TURNS
        assert response.extracted_facts == 1
        assert response.skipped_facts == 1
        assert response.failed_facts == 0
        mock_add_fact.assert_awaited_once()
        assert mock_audit.await_count == EXPECTED_AUDIT_EVENTS_FOR_EXTRACTION

    async def test_end_session_returns_closed_status_and_extraction_summary(self) -> None:
        """Session closure should trigger extraction and return a stable response contract."""
        extraction_response = SessionKnowledgeExtractionResponse(
            tenant_id="tenant_a",
            session_id="session_123",
            domain="general",
            processed_turns=3,
            extracted_facts=2,
            skipped_facts=1,
            failed_facts=0,
            extracted_at=datetime.now(UTC),
        )

        with (
            patch.object(MemoryAPI, "_mark_session_closed", return_value=True),
            patch.object(
                MemoryAPI,
                "record_audit_event",
                new=AsyncMock(),
            ) as mock_audit,
            patch.object(
                MemoryAPI,
                "extract_session_knowledge",
                new=AsyncMock(return_value=extraction_response),
            ) as mock_extract,
        ):
            response = await MemoryAPI.end_session(
                tenant_id="tenant_a",
                session_id="session_123",
                end_reason="timeout",
                window_size=30,
            )

        assert response.tenant_id == "tenant_a"
        assert response.session_id == "session_123"
        assert response.status == "closed"
        assert response.end_reason == "timeout"
        assert response.extraction_status == "completed"
        assert response.extraction.extracted_facts == EXPECTED_EXTRACTED_FACTS
        mock_extract.assert_awaited_once_with(
            tenant_id="tenant_a",
            session_id="session_123",
            domain_hint=None,
            window_size=30,
            authorization_scope=None,
        )
        mock_audit.assert_awaited_once()

    async def test_end_session_is_idempotent_when_already_closed(self) -> None:
        """Repeated session closure should not run extraction again."""
        with (
            patch.object(MemoryAPI, "_mark_session_closed", return_value=False),
            patch.object(
                MemoryAPI,
                "extract_session_knowledge",
                new=AsyncMock(),
            ) as mock_extract,
            patch.object(
                MemoryAPI,
                "record_audit_event",
                new=AsyncMock(),
            ) as mock_audit,
        ):
            response = await MemoryAPI.end_session(
                tenant_id="tenant_a",
                session_id="session_123",
                end_reason="completed",
            )

        assert response.status == "closed"
        assert response.extraction_status == "already_closed"
        assert response.extraction.extracted_facts == 0
        mock_extract.assert_not_awaited()
        mock_audit.assert_not_awaited()
