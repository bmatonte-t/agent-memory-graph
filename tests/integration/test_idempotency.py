"""Integration tests for idempotency context and deduplication."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.idempotency import (
    IdempotencyContext,
    generate_idempotency_key,
    get_idempotency_key,
    reset_idempotency_key,
    set_idempotency_key,
)
from src.memory.api import MemoryAPI
from src.models.schemas import FactResponse

TENANT_ID = "tenant_123"
UUID_LENGTH = 36
CONCURRENT_TASKS = 3


class TestIdempotency:
    """Integration tests for idempotency context and deduplication."""

    def test_generate_idempotency_key_creates_unique_keys(self) -> None:
        """Verify key generation creates unique UUID strings."""
        key1 = generate_idempotency_key()
        key2 = generate_idempotency_key()

        assert isinstance(key1, str)
        assert isinstance(key2, str)
        assert len(key1) == UUID_LENGTH
        assert len(key2) == UUID_LENGTH
        assert key1 != key2

    def test_idempotency_key_context_manager_sets_and_clears(self) -> None:
        """Verify IdempotencyContext sets and clears idempotency key."""
        # Initially None
        assert get_idempotency_key() is None

        # Enter context, key should be set
        with IdempotencyContext() as ctx:
            assert ctx.key is not None
            assert get_idempotency_key() == ctx.key
            assert len(ctx.key) == UUID_LENGTH

        # Exit context, key should be cleared
        assert get_idempotency_key() is None

    def test_idempotency_key_manual_set_and_reset(self) -> None:
        """Verify manual set and reset of idempotency key."""
        assert get_idempotency_key() is None

        # Manually set a key
        test_key = "test_key_12345678901234567890"
        token = set_idempotency_key(test_key)
        assert get_idempotency_key() == test_key

        # Reset with token
        reset_idempotency_key(token)
        assert get_idempotency_key() is None

    @pytest.mark.asyncio
    async def test_semantic_fact_creation_within_idempotency_context(
        self,
    ) -> None:
        """Verify semantic fact creation happens within idempotency context."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)
            mock_client.get_database.return_value = mock_db

            captured_keys: list[str | None] = []

            # Capture idempotency key inside batch operation
            def execute_update_with_capture(
                *args: Any,
                **kwargs: Any,
            ) -> int:
                """Capture the current idempotency key."""
                current_key = get_idempotency_key()
                if current_key is not None:
                    captured_keys.append(current_key)
                return 1

            mock_batch.execute_update.side_effect = execute_update_with_capture

            with patch.object(
                MemoryAPI,
                "_update_weight_on_successful_use",
                new_callable=AsyncMock,
            ):
                response = await MemoryAPI.add_semantic_fact(
                    tenant_id=TENANT_ID,
                    entity_type="PERSON",
                    entity_id="person_idempotency_test",
                )

                # Verify response is valid
                assert isinstance(response, FactResponse)
                assert response.tenant_id == TENANT_ID

                # Verify idempotency key was captured during batch operation
                assert len(captured_keys) > 0
                assert captured_keys[0] is not None
                assert len(captured_keys[0]) == UUID_LENGTH

    @pytest.mark.asyncio
    async def test_idempotency_context_not_active_after_fact_creation(
        self,
    ) -> None:
        """Verify idempotency context is cleared after add_semantic_fact."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)
            mock_client.get_database.return_value = mock_db

            with patch.object(
                MemoryAPI,
                "_update_weight_on_successful_use",
                new_callable=AsyncMock,
            ):
                await MemoryAPI.add_semantic_fact(
                    tenant_id=TENANT_ID,
                    entity_type="PERSON",
                    entity_id="person_after_context_test",
                )

                # After fact creation, context should be cleared
                assert get_idempotency_key() is None

    @pytest.mark.asyncio
    async def test_concurrent_operations_have_independent_idempotency_keys(
        self,
    ) -> None:
        """Verify concurrent operations get independent idempotency keys."""
        task_keys: dict[int, str] = {}

        async def task_with_key() -> None:
            """Create a semantic fact and capture its idempotency key."""
            with IdempotencyContext() as ctx:
                task_id = id(asyncio.current_task())
                task_keys[task_id] = ctx.key

                # Simulate async work
                await asyncio.sleep(0.01)

                # Verify key is still valid
                assert get_idempotency_key() == ctx.key

        # Run concurrent tasks
        tasks = [task_with_key() for _ in range(CONCURRENT_TASKS)]
        await asyncio.gather(*tasks)

        # Verify each task had a unique key
        unique_keys = set(task_keys.values())
        assert len(unique_keys) == CONCURRENT_TASKS

        # Verify all keys are valid UUID strings
        for key in task_keys.values():
            assert isinstance(key, str)
            assert len(key) == UUID_LENGTH

        # After concurrent execution, context should be cleared
        assert get_idempotency_key() is None

    def test_idempotency_context_survives_exception(self) -> None:
        """Verify idempotency context clears even if exception occurs."""
        assert get_idempotency_key() is None

        try:
            with IdempotencyContext() as ctx:
                assert get_idempotency_key() == ctx.key
                error = ValueError("Test exception")
                raise error
        except ValueError:
            pass

        # Context should be cleared even after exception
        assert get_idempotency_key() is None
