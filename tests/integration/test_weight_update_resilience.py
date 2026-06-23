"""Integration tests for weight update retry resilience."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.memory.api import MemoryAPI

TENANT_ID = "tenant_123"
TEST_NODE_IDS = ["node_1", "node_2", "node_3"]


class TestWeightUpdateResilience:
    """Integration tests for weight update retry behavior."""

    @pytest.mark.asyncio
    async def test_weight_update_executes_with_batch(self) -> None:
        """Verify weight update executes batch operations."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()

            def batch_context_manager() -> MagicMock:
                """Return batch context manager."""
                return MagicMock(
                    __enter__=MagicMock(return_value=mock_batch),
                    __exit__=MagicMock(return_value=None),
                )

            mock_db.batch.side_effect = batch_context_manager
            mock_client.get_database.return_value = mock_db

            with patch("src.memory.api.get_retry_policy") as mock_retry_policy:
                mock_policy = MagicMock()
                mock_policy.enabled = True
                mock_policy.max_attempts = 1
                mock_retry_policy.return_value = mock_policy

                with patch("src.memory.api.settings.governance.weighting") as mock_weighting:
                    mock_weighting.enabled = True
                    mock_weighting.should_trigger.return_value = True

                    await MemoryAPI._update_weight_on_successful_use(
                        TENANT_ID,
                        TEST_NODE_IDS,
                        session_action_count=5,
                    )

                    # Verify execute_update was called
                    assert mock_batch.execute_update.call_count == 1

    @pytest.mark.asyncio
    async def test_weight_update_disabled_skips_execution(self) -> None:
        """Verify weight update skips when disabled."""
        with patch("src.memory.api.settings.governance.weighting") as mock_weighting:
            mock_weighting.enabled = False

            # Should return early without calling Spanner
            with patch("src.memory.api.SpannerClient") as mock_client:
                await MemoryAPI._update_weight_on_successful_use(
                    TENANT_ID,
                    TEST_NODE_IDS,
                    session_action_count=5,
                )

                # Spanner should not be called
                mock_client.get_database.assert_not_called()

    @pytest.mark.asyncio
    async def test_weight_update_below_trigger_threshold_skips(self) -> None:
        """Verify weight update skips when should_trigger returns False."""
        with patch("src.memory.api.settings.governance.weighting") as mock_weighting:
            mock_weighting.enabled = True
            mock_weighting.should_trigger.return_value = False

            with patch("src.memory.api.SpannerClient") as mock_client:
                await MemoryAPI._update_weight_on_successful_use(
                    TENANT_ID,
                    TEST_NODE_IDS,
                    session_action_count=5,
                )

                # Spanner should not be called
                mock_client.get_database.assert_not_called()

    @pytest.mark.asyncio
    async def test_weight_update_with_multiple_node_ids(self) -> None:
        """Verify weight update processes multiple node IDs in batch."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()

            def batch_context_manager() -> MagicMock:
                """Return batch context manager."""
                return MagicMock(
                    __enter__=MagicMock(return_value=mock_batch),
                    __exit__=MagicMock(return_value=None),
                )

            mock_db.batch.side_effect = batch_context_manager
            mock_client.get_database.return_value = mock_db

            with patch("src.memory.api.get_retry_policy") as mock_retry_policy:
                mock_policy = MagicMock()
                mock_policy.enabled = True
                mock_policy.max_attempts = 1
                mock_retry_policy.return_value = mock_policy

                with patch("src.memory.api.settings.governance.weighting") as mock_weighting:
                    mock_weighting.enabled = True
                    mock_weighting.should_trigger.return_value = True

                    node_ids = ["node_1", "node_2", "node_3", "node_4", "node_5"]
                    await MemoryAPI._update_weight_on_successful_use(
                        TENANT_ID,
                        node_ids,
                        session_action_count=10,
                    )

                    # Verify execute_update was called
                    assert mock_batch.execute_update.call_count == 1
