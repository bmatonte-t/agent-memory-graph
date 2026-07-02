"""Integration tests for idempotency context and deduplication."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

import src.memory.api as memory_api
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


@dataclass(slots=True)
class _BatchStub:
    """Batch stub used to track idempotency key usage."""

    captured_keys: list[str | None] = field(default_factory=list)

    def execute_update(self, sql: str, params: dict[str, object]) -> int:
        """Capture active idempotency key for each write operation.

        Args:
            sql: SQL statement.
            params: Bound SQL parameters.

        Returns:
            int: Number of affected rows.
        """
        del sql, params
        self.captured_keys.append(get_idempotency_key())
        return 1


class _BatchContext:
    """Context manager wrapper around batch stub."""

    def __init__(self, batch: _BatchStub) -> None:
        """Store wrapped batch.

        Args:
            batch: Batch stub instance.
        """
        self._batch = batch

    def __enter__(self) -> _BatchStub:
        """Return wrapped batch.

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


@dataclass(slots=True)
class _DatabaseStub:
    """Database stub exposing batch writes used in the tested flow."""

    batch_stub: _BatchStub = field(default_factory=_BatchStub)

    def batch(self) -> _BatchContext:
        """Return writable batch context.

        Returns:
            _BatchContext: Writable context over batch stub.
        """
        return _BatchContext(self.batch_stub)

    def run_in_transaction(self, operation: object) -> object:
        """Execute transaction callback against batch stub.

        Args:
            operation: Transaction callback.

        Returns:
            object: Callback result.
        """
        if not callable(operation):
            msg = "operation must be callable"
            raise TypeError(msg)
        return operation(self.batch_stub)


class _SpannerClientStub:
    """Spanner client stub for idempotency integration tests."""

    _database = _DatabaseStub()

    @staticmethod
    def get_database() -> _DatabaseStub:
        """Return shared in-memory database.

        Returns:
            _DatabaseStub: Shared database stub.
        """
        return _SpannerClientStub._database

    @staticmethod
    def _validate_audit_mutation_forbidden(table_name: str, operation: str) -> None:
        """Allow append-only audit inserts in integration tests.

        Args:
            table_name: Target table name.
            operation: Requested mutation operation.
        """
        del table_name, operation


class TestIdempotency:
    """Integration tests for idempotency context and deduplication."""

    @pytest.fixture(autouse=True)
    def _configure_stubs(self) -> object:
        """Inject deterministic Spanner and weight-update stubs."""
        _SpannerClientStub._database = _DatabaseStub()
        original_spanner_client = memory_api.SpannerClient
        original_weight_update = MemoryAPI._update_weight_on_successful_use

        async def _noop_weight_update(*args: object, **kwargs: object) -> None:
            """No-op weight update used by idempotency integration tests."""
            del args, kwargs

        memory_api.SpannerClient = _SpannerClientStub
        MemoryAPI._update_weight_on_successful_use = _noop_weight_update

        try:
            yield
        finally:
            memory_api.SpannerClient = original_spanner_client
            MemoryAPI._update_weight_on_successful_use = original_weight_update

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
        response = await MemoryAPI.add_semantic_fact(
            tenant_id=TENANT_ID,
            entity_type="PERSON",
            entity_id="person_idempotency_test",
        )

        assert isinstance(response, FactResponse)
        assert response.tenant_id == TENANT_ID

        captured_keys = _SpannerClientStub.get_database().batch_stub.captured_keys
        non_empty_keys = [key for key in captured_keys if key is not None]
        assert non_empty_keys
        assert len(non_empty_keys[0]) == UUID_LENGTH

    @pytest.mark.asyncio
    async def test_idempotency_context_not_active_after_fact_creation(
        self,
    ) -> None:
        """Verify idempotency context is cleared after add_semantic_fact."""
        await MemoryAPI.add_semantic_fact(
            tenant_id=TENANT_ID,
            entity_type="PERSON",
            entity_id="person_after_context_test",
        )

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
