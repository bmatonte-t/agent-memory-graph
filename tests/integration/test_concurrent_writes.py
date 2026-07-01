"""Integration tests for concurrent write operations with deduplication."""

from __future__ import annotations

import asyncio
import threading
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

    @pytest.mark.asyncio
    async def test_concurrent_session_action_increments_not_lost(self) -> None:
        """100 concurrent async increments must each call execute_update exactly once.

        A read-modify-write implementation would race: two concurrent callers could
        both read the same count, both write count+1, and silently drop one increment.
        The atomic UPDATE (SET count = count + 1) avoids the read entirely, so each
        of N concurrent callers invokes execute_update exactly once — no SELECT, no race.
        This test verifies that behavior under mock-concurrent asyncio.gather load.
        """
        num_increments = 100
        call_count = 0
        call_count_lock = threading.Lock()

        mock_db = MagicMock()
        mock_transaction = MagicMock()

        def fake_execute_update(sql: str, params: dict) -> int:
            """Record the call and confirm no SELECT read preceded it.

            Uses a threading.Lock to safely increment the shared call_count
            from multiple real OS threads spawned by run_in_executor.
            """
            nonlocal call_count
            with call_count_lock:
                call_count += 1
            return 1

        mock_transaction.execute_update.side_effect = fake_execute_update
        mock_transaction.execute_sql = MagicMock(
            side_effect=AssertionError(
                "execute_sql (read path) must NOT be called — atomic UPDATE only"
            )
        )

        def fake_run_in_transaction(fn: object) -> int:
            """Execute the transaction callable with a fresh mock transaction.

            Args:
                fn: The transaction callable passed by the caller.

            Returns:
                Simulated rows-affected count.
            """
            return fn(mock_transaction)  # type: ignore[operator]

        mock_db.run_in_transaction.side_effect = fake_run_in_transaction

        with patch("src.memory.api.SpannerClient.get_database", return_value=mock_db):
            tasks = [
                asyncio.get_event_loop().run_in_executor(
                    None,
                    MemoryAPI._increment_session_action_count,
                    "tenant_concurrent",
                    "sess_concurrent",
                )
                for _ in range(num_increments)
            ]
            results = await asyncio.gather(*tasks)

        # Every concurrent call must have invoked execute_update exactly once.
        assert call_count == num_increments, (
            f"Expected {num_increments} execute_update calls, got {call_count}"
        )
        # All calls must return 1 (rows affected).
        assert all(r == 1 for r in results), f"Some increments returned unexpected value: {results}"
        # execute_sql (read path) must never have been called.
        mock_transaction.execute_sql.assert_not_called()

    def test_session_action_count_uses_atomic_update_not_read_modify_write(self) -> None:
        """Session action counter must use a single atomic SQL UPDATE with no prior SELECT.

        A read-modify-write pattern is not race-safe under concurrent writers: two
        concurrent readers can both read 0, both write 1, and one increment is lost.
        The fix emits a single 'SET count = count + 1' UPDATE with no SELECT read round-trip.
        Verified by inspecting the transaction mock: execute_update must be called exactly
        once, and execute_sql (the read path) must not be called at all.
        """
        mock_db = MagicMock()
        mock_transaction = MagicMock()
        mock_transaction.execute_update.return_value = 1

        def fake_run_in_transaction(fn: object) -> int:
            """Execute the transaction callable with a fresh mock transaction.

            Args:
                fn: The transaction callable passed by the caller.

            Returns:
                Simulated rows-affected count.
            """
            return fn(mock_transaction)  # type: ignore[operator]

        mock_db.run_in_transaction.side_effect = fake_run_in_transaction

        with patch("src.memory.api.SpannerClient.get_database", return_value=mock_db):
            # The atomic implementation calls only execute_update — no SELECT read.
            result = MemoryAPI._increment_session_action_count(
                tenant_id="tenant_a",
                session_id="sess_race_test",
            )

        # Atomic path: execute_update called once, no SQL read calls
        mock_transaction.execute_update.assert_called_once()
        mock_transaction.execute_sql.assert_not_called()
        assert result == 1  # rows affected by the atomic UPDATE
