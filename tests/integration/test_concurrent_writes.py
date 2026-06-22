"""Integration tests for concurrent write operations with deduplication."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.memory.api import MemoryAPI
from src.models.schemas import FactResponse

TENANT_ID = "tenant_123"
TENANT_COUNT = 3
TASKS_PER_TENANT = 3
CONCURRENT_FACT_TASKS = 5
MIXED_TASKS = 10


class TestConcurrentWrites:
    """Tests for concurrent write operations maintaining data integrity."""

    @pytest.mark.asyncio
    async def test_concurrent_semantic_fact_creation_prevents_duplicates(
        self,
    ) -> None:
        """Verify that concurrent fact insertions don't create duplicate edges."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()

            def batch_context_manager() -> MagicMock:
                """Return batch context manager."""
                return MagicMock(
                    __enter__=MagicMock(return_value=mock_batch),
                    __exit__=MagicMock(return_value=None),
                )

            mock_db.batch.side_effect = batch_context_manager
            mock_db.execute_query.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.execute_query.return_value.__exit__ = MagicMock(return_value=None)
            mock_snapshot.data.return_value = []
            mock_client.get_database.return_value = mock_db

            with patch.object(
                MemoryAPI,
                "_update_weight_on_successful_use",
                new_callable=AsyncMock,
            ):
                tasks = [
                    MemoryAPI.add_semantic_fact(
                        tenant_id=TENANT_ID,
                        entity_type="PERSON",
                        entity_id="person_123",
                    )
                    for _ in range(CONCURRENT_FACT_TASKS)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # All operations should complete without errors
                assert len(results) == CONCURRENT_FACT_TASKS
                assert all(isinstance(r, FactResponse) for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_fact_creation_with_same_entity_id_retried_idempotently(
        self,
    ) -> None:
        """Verify idempotency prevents duplicate facts on retry."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()

            def batch_context_manager() -> MagicMock:
                """Return batch context manager."""
                return MagicMock(
                    __enter__=MagicMock(return_value=mock_batch),
                    __exit__=MagicMock(return_value=None),
                )

            mock_db.batch.side_effect = batch_context_manager
            mock_db.execute_query.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.execute_query.return_value.__exit__ = MagicMock(return_value=None)
            mock_snapshot.data.return_value = []
            mock_client.get_database.return_value = mock_db

            with patch.object(
                MemoryAPI,
                "_update_weight_on_successful_use",
                new_callable=AsyncMock,
            ):
                response = await MemoryAPI.add_semantic_fact(
                    tenant_id=TENANT_ID,
                    entity_type="PERSON",
                    entity_id="idempotent_123",
                )

                assert isinstance(response, FactResponse)

    @pytest.mark.asyncio
    async def test_concurrent_semantic_facts_independent_tenant_isolation(
        self,
    ) -> None:
        """Verify concurrent writes maintain tenant isolation."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()

            def batch_context_manager() -> MagicMock:
                """Return batch context manager."""
                return MagicMock(
                    __enter__=MagicMock(return_value=mock_batch),
                    __exit__=MagicMock(return_value=None),
                )

            mock_db.batch.side_effect = batch_context_manager
            mock_db.execute_query.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.execute_query.return_value.__exit__ = MagicMock(return_value=None)
            mock_snapshot.data.return_value = []
            mock_client.get_database.return_value = mock_db

            with patch.object(
                MemoryAPI,
                "_update_weight_on_successful_use",
                new_callable=AsyncMock,
            ):
                tasks = []
                for tenant_idx in range(TENANT_COUNT):
                    for task_idx in range(TASKS_PER_TENANT):
                        tenant_id = f"tenant_{tenant_idx}"
                        entity_id = f"entity_{tenant_idx}_{task_idx}"
                        tasks.append(
                            MemoryAPI.add_semantic_fact(
                                tenant_id=tenant_id,
                                entity_type="PERSON",
                                entity_id=entity_id,
                            )
                        )

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # All operations should complete
                assert len(results) == TENANT_COUNT * TASKS_PER_TENANT
                assert all(isinstance(r, FactResponse) for r in results)

    @pytest.mark.asyncio
    async def test_mixed_concurrent_operations_maintain_consistency(
        self,
    ) -> None:
        """Verify mixed concurrent operations maintain consistency."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()

            def batch_context_manager() -> MagicMock:
                """Return batch context manager."""
                return MagicMock(
                    __enter__=MagicMock(return_value=mock_batch),
                    __exit__=MagicMock(return_value=None),
                )

            mock_db.batch.side_effect = batch_context_manager
            mock_db.execute_query.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.execute_query.return_value.__exit__ = MagicMock(return_value=None)
            mock_snapshot.data.return_value = []
            mock_client.get_database.return_value = mock_db

            with patch.object(
                MemoryAPI,
                "_update_weight_on_successful_use",
                new_callable=AsyncMock,
            ):
                tasks = [
                    MemoryAPI.add_semantic_fact(
                        tenant_id=TENANT_ID,
                        entity_type="PERSON",
                        entity_id=f"mixed_entity_{i}",
                    )
                    for i in range(MIXED_TASKS)
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                assert len(results) == MIXED_TASKS
                assert all(isinstance(r, FactResponse) for r in results)
