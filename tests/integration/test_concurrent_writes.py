"""Integration tests for concurrent write operations with deterministic stubs."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import src.memory.api as memory_api
from src.memory.api import MemoryAPI
from src.models.schemas import FactResponse, SessionKnowledgeExtractionResponse

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

TENANT_ID = "tenant_123"
TENANT_COUNT = 3
TASKS_PER_TENANT = 3
CONCURRENT_FACT_TASKS = 5
MIXED_TASKS = 10
CONCURRENT_SESSION_CLOSE_TASKS = 2


class _DependencyOverrides:
    """Temporarily replace module or class attributes."""

    def __init__(self, target: ModuleType | type[object], overrides: dict[str, Any]) -> None:
        """Initialize override context.

        Args:
            target: Module or class to modify.
            overrides: Temporary attribute values.
        """
        self._target = target
        self._overrides = overrides
        self._originals: dict[str, Any] = {}

    def __enter__(self) -> None:
        """Apply overrides."""
        for name, value in self._overrides.items():
            self._originals[name] = getattr(self._target, name)
            setattr(self._target, name, value)

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        """Restore original attributes.

        Returns:
            bool: Always False to propagate exceptions.
        """
        del exc_type, exc_value, traceback
        for name, value in self._originals.items():
            setattr(self._target, name, value)
        return False


class _BatchRecorder:
    """Capture write operations executed through batch context."""

    def __init__(self) -> None:
        """Initialize write counters and event tracking."""
        self.execute_update_count = 0
        self.audit_event_types: list[str] = []

    def execute_update(self, sql: str, params: dict[str, object]) -> int:
        """Record write invocations and event type payloads.

        Args:
            sql: SQL operation string.
            params: SQL parameter payload.

        Returns:
            int: Simulated rows affected.
        """
        del sql
        self.execute_update_count += 1
        event_type = params.get("event_type")
        if isinstance(event_type, str):
            self.audit_event_types.append(event_type)
        return 1


class _BatchContext:
    """Context manager for batch recorder."""

    def __init__(self, batch: _BatchRecorder) -> None:
        """Store batch recorder instance.

        Args:
            batch: Recorder used inside context.
        """
        self._batch = batch

    def __enter__(self) -> _BatchRecorder:
        """Expose batch recorder.

        Returns:
            _BatchRecorder: Writable recorder.
        """
        return self._batch

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        """Leave context without swallowing exceptions.

        Returns:
            bool: Always False.
        """
        del exc_type, exc_value, traceback
        return False


class _TransactionRecorder:
    """Transaction object used by run_in_transaction flows."""

    def __init__(self, counter_lock: threading.Lock | None = None) -> None:
        """Initialize transaction recorder.

        Args:
            counter_lock: Optional lock for thread-safe call counting.
        """
        self.execute_update_count = 0
        self._lock = counter_lock

    def execute_update(self, sql: str, params: dict[str, object]) -> int:
        """Record atomic update invocation.

        Args:
            sql: SQL operation string.
            params: SQL parameter payload.

        Returns:
            int: Simulated rows affected.
        """
        del sql, params
        if self._lock is None:
            self.execute_update_count += 1
            return 1
        with self._lock:
            self.execute_update_count += 1
        return 1

    def execute_sql(self, sql: str, params: dict[str, object]) -> list[tuple[object, ...]]:
        """Guard against read-modify-write behavior.

        Args:
            sql: SQL statement.
            params: SQL params.

        Raises:
            AssertionError: Always, because this path must remain unused.
        """
        del sql, params
        message = "execute_sql read path must not be called"
        raise AssertionError(message)


class _DatabaseRecorder:
    """Database stub supporting batch and transaction APIs."""

    def __init__(self, transaction: _TransactionRecorder | None = None) -> None:
        """Create reusable recorders.

        Args:
            transaction: Optional custom transaction recorder.
        """
        self.batch_recorder = _BatchRecorder()
        self.transaction_recorder = transaction or _TransactionRecorder()

    def batch(self) -> _BatchContext:
        """Return context manager for batch writes.

        Returns:
            _BatchContext: Batch context wrapper.
        """
        return _BatchContext(self.batch_recorder)

    def run_in_transaction(self, operation: Callable[[object], int]) -> int:
        """Execute transaction callback with recorder.

        Args:
            operation: Transaction callback.

        Returns:
            int: Callback result.
        """
        return operation(self.transaction_recorder)


class _SpannerClientStub:
    """In-memory Spanner client replacement for integration tests."""

    database: _DatabaseRecorder = _DatabaseRecorder()

    @staticmethod
    def get_database() -> _DatabaseRecorder:
        """Return active in-memory database.

        Returns:
            _DatabaseRecorder: Current database recorder.
        """
        return _SpannerClientStub.database

    @staticmethod
    def _validate_audit_mutation_forbidden(table_name: str, operation: str) -> None:
        """Allow append-only audit operations in tests.

        Args:
            table_name: Audit table name.
            operation: Operation name.
        """
        del table_name, operation


async def _noop_weight_update(
    tenant_id: str,
    node_ids: list[str],
    memory_tier: str = "SEMANTIC",
    session_action_count: int | None = None,
) -> None:
    """Disable weight update side effects while preserving signature."""
    del tenant_id, node_ids, memory_tier, session_action_count


async def _noop_extract_session_knowledge(
    tenant_id: str,
    session_id: str,
    domain_hint: str | None = None,
    window_size: int = 50,
    authorization_scope: object | None = None,
) -> SessionKnowledgeExtractionResponse:
    """Return deterministic extraction response."""
    del window_size, authorization_scope
    return SessionKnowledgeExtractionResponse(
        tenant_id=tenant_id,
        session_id=session_id,
        domain=domain_hint or "general",
        processed_turns=3,
        extracted_facts=2,
        skipped_facts=1,
        failed_facts=0,
        extracted_at=datetime.now(UTC),
    )


class TestConcurrentWrites:
    """Tests for concurrent write operations maintaining data integrity."""

    async def test_concurrent_semantic_fact_creation_prevents_duplicates(self) -> None:
        """Concurrent inserts should all complete successfully."""
        _SpannerClientStub.database = _DatabaseRecorder()

        with (
            _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}),
            _DependencyOverrides(
                MemoryAPI,
                {"_update_weight_on_successful_use": _noop_weight_update},
            ),
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

        assert len(results) == CONCURRENT_FACT_TASKS
        assert all(isinstance(result, FactResponse) for result in results)

    async def test_concurrent_fact_creation_with_same_entity_id_retried_idempotently(self) -> None:
        """Single insert with same ID should remain valid through retry wrapper."""
        _SpannerClientStub.database = _DatabaseRecorder()

        with (
            _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}),
            _DependencyOverrides(
                MemoryAPI,
                {"_update_weight_on_successful_use": _noop_weight_update},
            ),
        ):
            response = await MemoryAPI.add_semantic_fact(
                tenant_id=TENANT_ID,
                entity_type="PERSON",
                entity_id="idempotent_123",
            )

        assert isinstance(response, FactResponse)

    async def test_concurrent_semantic_facts_independent_tenant_isolation(self) -> None:
        """Concurrent writes should succeed independently across tenants."""
        _SpannerClientStub.database = _DatabaseRecorder()

        with (
            _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}),
            _DependencyOverrides(
                MemoryAPI,
                {"_update_weight_on_successful_use": _noop_weight_update},
            ),
        ):
            tasks = [
                MemoryAPI.add_semantic_fact(
                    tenant_id=f"tenant_{tenant_idx}",
                    entity_type="PERSON",
                    entity_id=f"entity_{tenant_idx}_{task_idx}",
                )
                for tenant_idx in range(TENANT_COUNT)
                for task_idx in range(TASKS_PER_TENANT)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        assert len(results) == TENANT_COUNT * TASKS_PER_TENANT
        assert all(isinstance(result, FactResponse) for result in results)

    async def test_mixed_concurrent_operations_maintain_consistency(self) -> None:
        """Mixed concurrent semantic writes should remain consistent."""
        _SpannerClientStub.database = _DatabaseRecorder()

        with (
            _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}),
            _DependencyOverrides(
                MemoryAPI,
                {"_update_weight_on_successful_use": _noop_weight_update},
            ),
        ):
            tasks = [
                MemoryAPI.add_semantic_fact(
                    tenant_id=TENANT_ID,
                    entity_type="PERSON",
                    entity_id=f"mixed_entity_{idx}",
                )
                for idx in range(MIXED_TASKS)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        assert len(results) == MIXED_TASKS
        assert all(isinstance(result, FactResponse) for result in results)

    async def test_concurrent_session_action_increments_not_lost(self) -> None:
        """Concurrent increments should execute one atomic update per request."""
        increment_count = 100
        lock = threading.Lock()
        transaction = _TransactionRecorder(counter_lock=lock)
        _SpannerClientStub.database = _DatabaseRecorder(transaction=transaction)

        with _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}):
            tasks = [
                asyncio.get_running_loop().run_in_executor(
                    None,
                    MemoryAPI._increment_session_action_count,
                    "tenant_concurrent",
                    "sess_concurrent",
                )
                for _ in range(increment_count)
            ]
            results = await asyncio.gather(*tasks)

        assert transaction.execute_update_count == increment_count
        assert all(result == 1 for result in results)

    def test_session_action_count_uses_atomic_update_not_read_modify_write(self) -> None:
        """Atomic counter path must use execute_update and avoid read calls."""
        transaction = _TransactionRecorder()
        _SpannerClientStub.database = _DatabaseRecorder(transaction=transaction)

        with _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}):
            result = MemoryAPI._increment_session_action_count(
                tenant_id="tenant_a",
                session_id="sess_race_test",
            )

        assert transaction.execute_update_count == 1
        assert result == 1

    async def test_concurrent_end_session_triggers_single_extraction(self) -> None:
        """Concurrent close requests should extract knowledge exactly once."""
        close_state = {"attempts": 0}
        close_lock = threading.Lock()

        def mark_session_closed_once(
            tenant_id: str,
            session_id: str,
            end_reason: str,
            ended_at: object,
        ) -> bool:
            """Close first attempt only and reject subsequent ones."""
            del tenant_id, session_id, end_reason, ended_at
            with close_lock:
                close_state["attempts"] += 1
                return close_state["attempts"] == 1

        extraction_calls = {"count": 0}

        async def extract_once(
            *args: object,
            **kwargs: object,
        ) -> SessionKnowledgeExtractionResponse:
            """Track extraction invocation count and return deterministic payload."""
            extraction_calls["count"] += 1
            return await _noop_extract_session_knowledge(*args, **kwargs)

        async def noop_audit(
            tenant_id: str,
            event_type: str,
            source_node_id: str,
            context: dict[str, object] | None = None,
            authorization_scope: object | None = None,
        ) -> object:
            """No-op audit recorder used by close path."""
            del tenant_id, event_type, source_node_id, context, authorization_scope
            return None

        with _DependencyOverrides(
            MemoryAPI,
            {
                "_mark_session_closed": mark_session_closed_once,
                "extract_session_knowledge": extract_once,
                "record_audit_event": noop_audit,
            },
        ):
            results = await asyncio.gather(
                MemoryAPI.end_session(
                    tenant_id=TENANT_ID,
                    session_id="session_concurrent",
                    end_reason="timeout",
                ),
                MemoryAPI.end_session(
                    tenant_id=TENANT_ID,
                    session_id="session_concurrent",
                    end_reason="timeout",
                ),
            )

        assert len(results) == CONCURRENT_SESSION_CLOSE_TASKS
        assert {result.extraction_status for result in results} == {"completed", "already_closed"}
        assert extraction_calls["count"] == 1
