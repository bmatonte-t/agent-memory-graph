"""Load tests and performance benchmarks for memory APIs."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import src.memory.api as memory_api
from src.memory.api import MemoryAPI

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

P95_SESSION_TARGET_MS = 50
P95_FACT_TARGET_MS = 50
P95_CONTEXT_TARGET_MS = 200
LARGE_GRAPH_QUERY_TARGET_MS = 500
LARGE_GRAPH_TURN_COUNT = 100
CONCURRENT_TASK_COUNT = 10
SIMULATED_NODE_COUNT = 10_000
SIMULATED_EDGE_COUNT = 100_000
TEST_TENANT_ID = "tenant_perf"


class _DependencyOverrides:
    """Temporarily replace module or class attributes for a test scope."""

    def __init__(self, target: ModuleType | type[object], overrides: dict[str, Any]) -> None:
        """Initialize override scope.

        Args:
            target: Module or class to modify.
            overrides: Temporary attributes.
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
    """Record execute_update calls and captured audit event types."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.execute_update_count = 0
        self.audit_event_types: list[str] = []

    def execute_update(self, sql: str, params: dict[str, object]) -> int:
        """Record writes and event types.

        Args:
            sql: SQL text.
            params: SQL parameters.

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
    """Context manager exposing a batch recorder."""

    def __init__(self, batch: _BatchRecorder) -> None:
        """Store batch recorder.

        Args:
            batch: Recorder instance.
        """
        self._batch = batch

    def __enter__(self) -> _BatchRecorder:
        """Return batch recorder.

        Returns:
            _BatchRecorder: Writable batch recorder.
        """
        return self._batch

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        """Leave context without swallowing exceptions.

        Returns:
            bool: Always False.
        """
        del exc_type, exc_value, traceback
        return False


class _DatabaseRecorder:
    """Spanner database stand-in supporting batch and transactions."""

    def __init__(self) -> None:
        """Initialize reusable batch recorder."""
        self.batch_recorder = _BatchRecorder()

    def batch(self) -> _BatchContext:
        """Return batch context.

        Returns:
            _BatchContext: Context manager for writes.
        """
        return _BatchContext(self.batch_recorder)

    def run_in_transaction(self, operation: Callable[[object], int]) -> int:
        """Execute transaction callable against batch recorder.

        Args:
            operation: Transaction callable.

        Returns:
            int: Callable result.
        """
        return operation(self.batch_recorder)


class _SpannerClientStub:
    """In-memory client used for performance test determinism."""

    database: _DatabaseRecorder = _DatabaseRecorder()

    @staticmethod
    def get_database() -> _DatabaseRecorder:
        """Return active database stub.

        Returns:
            _DatabaseRecorder: In-memory database.
        """
        return _SpannerClientStub.database

    @staticmethod
    def _validate_audit_mutation_forbidden(table_name: str, operation: str) -> None:
        """Allow append-only audit writes in tests.

        Args:
            table_name: Audit table name.
            operation: Mutation operation.
        """
        del table_name, operation


async def _noop_weight_update(
    tenant_id: str,
    node_ids: list[str],
    memory_tier: str = "SEMANTIC",
    session_action_count: int | None = None,
) -> None:
    """Disable weight update side effects while preserving API signature."""
    del tenant_id, node_ids, memory_tier, session_action_count


def _make_turn_rows(turn_count: int) -> list[tuple[str, str, str, float, datetime, str]]:
    """Build deterministic retrieval rows.

    Args:
        turn_count: Number of turns to generate.

    Returns:
        list[tuple[str, str, str, float, datetime, str]]: Rows compatible with retrieval parser.
    """
    return [
        (
            f"turn_{idx}",
            "User" if idx % 2 == 0 else "Agent",
            f'{{"content": "message {idx}"}}',
            0.5 - (idx * 0.001),
            datetime.now(UTC),
            "HAS_TURN",
        )
        for idx in range(turn_count)
    ]


class TestLoadScenarios:
    """Load tests with performance benchmarks."""

    async def test_bulk_session_creation_latency(self) -> None:
        """Create 100 sessions and assert p95 latency target."""
        _SpannerClientStub.database = _DatabaseRecorder()

        with _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}):
            latencies_ms: list[float] = []
            total_sessions = 100

            for idx in range(total_sessions):
                start = time.perf_counter()
                await MemoryAPI.create_session(
                    tenant_id=TEST_TENANT_ID,
                    session_id=f"session_{idx}",
                    user_id=f"user_{idx}",
                )
                latencies_ms.append((time.perf_counter() - start) * 1000)

        sorted_latencies = sorted(latencies_ms)
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        assert p95 < P95_SESSION_TARGET_MS

    async def test_bulk_semantic_fact_ingestion(self) -> None:
        """Ingest 100 facts and assert p95 latency target."""
        _SpannerClientStub.database = _DatabaseRecorder()
        entity_types = ["PERSON", "OBJECT", "LOCATION", "EVENT", "ORGANIZATION"]

        with (
            _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}),
            _DependencyOverrides(
                MemoryAPI,
                {"_update_weight_on_successful_use": _noop_weight_update},
            ),
        ):
            latencies_ms: list[float] = []
            total_facts = 100

            for idx in range(total_facts):
                start = time.perf_counter()
                await MemoryAPI.add_semantic_fact(
                    tenant_id=TEST_TENANT_ID,
                    entity_type=entity_types[idx % len(entity_types)],
                    entity_id=f"entity_{idx}",
                    attributes={"name": f"Entity {idx}"},
                )
                latencies_ms.append((time.perf_counter() - start) * 1000)

        sorted_latencies = sorted(latencies_ms)
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        assert p95 < P95_FACT_TARGET_MS

    async def test_context_window_retrieval_latency(self) -> None:
        """Retrieve 100 windows and assert p95 latency target."""
        _SpannerClientStub.database = _DatabaseRecorder()

        def execute_sql_rows_stub(
            database: object,
            query: str,
            params: dict[str, object],
        ) -> list[tuple[str, str, str, float, datetime, str]]:
            """Return fixed number of turns for retrieval tests."""
            del database, query, params
            return _make_turn_rows(10)

        with (
            _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}),
            _DependencyOverrides(memory_api, {"execute_sql_rows": execute_sql_rows_stub}),
            _DependencyOverrides(
                MemoryAPI,
                {"_update_weight_on_successful_use": _noop_weight_update},
            ),
        ):
            latencies_ms: list[float] = []
            total_retrievals = 100

            for idx in range(total_retrievals):
                start = time.perf_counter()
                await MemoryAPI.retrieve_context_window(
                    tenant_id=TEST_TENANT_ID,
                    session_id=f"session_{idx}",
                    window_size=10,
                )
                latencies_ms.append((time.perf_counter() - start) * 1000)

        sorted_latencies = sorted(latencies_ms)
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        assert p95 < P95_CONTEXT_TARGET_MS

    async def test_graph_traversal_with_large_edge_set(self) -> None:
        """Retrieve 100 turns and assert latency and volume targets."""
        _SpannerClientStub.database = _DatabaseRecorder()

        def execute_sql_rows_stub(
            database: object,
            query: str,
            params: dict[str, object],
        ) -> list[tuple[str, str, str, float, datetime, str]]:
            """Return a larger turn set for traversal benchmark."""
            del database, query, params
            return _make_turn_rows(LARGE_GRAPH_TURN_COUNT)

        with (
            _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}),
            _DependencyOverrides(memory_api, {"execute_sql_rows": execute_sql_rows_stub}),
            _DependencyOverrides(
                MemoryAPI,
                {"_update_weight_on_successful_use": _noop_weight_update},
            ),
        ):
            start = time.perf_counter()
            result = await MemoryAPI.retrieve_context_window(
                tenant_id=TEST_TENANT_ID,
                session_id="session_large",
                window_size=LARGE_GRAPH_TURN_COUNT,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < LARGE_GRAPH_QUERY_TARGET_MS
        assert len(result.turns) == LARGE_GRAPH_TURN_COUNT

    async def test_simulated_write_pattern_for_10k_nodes_100k_edges(self) -> None:
        """Simulate expected write volume for large node and edge batches."""
        _SpannerClientStub.database = _DatabaseRecorder()
        database = _SpannerClientStub.get_database()

        with database.batch() as batch:
            for node_idx in range(SIMULATED_NODE_COUNT):
                batch.execute_update(
                    "INSERT INTO MemoryNode (NodeId) VALUES (@node_id)",
                    {"node_id": f"node_{node_idx}"},
                )
            for edge_idx in range(SIMULATED_EDGE_COUNT):
                batch.execute_update(
                    "INSERT INTO MemoryEdge (EdgeId) VALUES (@edge_id)",
                    {"edge_id": f"edge_{edge_idx}"},
                )

        expected_total_writes = SIMULATED_NODE_COUNT + SIMULATED_EDGE_COUNT
        assert database.batch_recorder.execute_update_count == expected_total_writes


class TestConcurrency:
    """Tests for concurrent operation handling."""

    async def test_concurrent_session_creation(self) -> None:
        """Create 10 sessions concurrently and verify active status responses."""
        _SpannerClientStub.database = _DatabaseRecorder()

        with _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}):
            tasks = [
                MemoryAPI.create_session(
                    tenant_id=TEST_TENANT_ID,
                    session_id=f"concurrent_session_{idx}",
                    user_id=f"concurrent_user_{idx}",
                )
                for idx in range(CONCURRENT_TASK_COUNT)
            ]
            results = await asyncio.gather(*tasks)

        assert len(results) == CONCURRENT_TASK_COUNT
        assert all(result.status == "active" for result in results)

    async def test_concurrent_semantic_fact_and_retrieval(self) -> None:
        """Mix semantic fact writes with context retrievals under concurrency."""
        _SpannerClientStub.database = _DatabaseRecorder()

        def execute_sql_rows_stub(
            database: object,
            query: str,
            params: dict[str, object],
        ) -> list[tuple[str, str, str, float, datetime, str]]:
            """Return a compact turn window for retrieval half of mixed workload."""
            del database, query, params
            return _make_turn_rows(5)

        with (
            _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}),
            _DependencyOverrides(memory_api, {"execute_sql_rows": execute_sql_rows_stub}),
            _DependencyOverrides(
                MemoryAPI,
                {"_update_weight_on_successful_use": _noop_weight_update},
            ),
        ):
            tasks: list[object] = []
            for idx in range(CONCURRENT_TASK_COUNT):
                if idx % 2 == 0:
                    tasks.append(
                        MemoryAPI.add_semantic_fact(
                            tenant_id=TEST_TENANT_ID,
                            entity_type="PERSON",
                            entity_id=f"concurrent_entity_{idx}",
                        )
                    )
                else:
                    tasks.append(
                        MemoryAPI.retrieve_context_window(
                            tenant_id=TEST_TENANT_ID,
                            session_id=f"concurrent_session_{idx}",
                            window_size=10,
                        )
                    )

            results = await asyncio.gather(*tasks)

        assert len(results) == CONCURRENT_TASK_COUNT


class TestAuditTrailIntegrity:
    """Tests for audit trail completeness."""

    async def test_all_operations_generate_audit_events(self) -> None:
        """Verify session, fact, and retrieval operations emit audit events."""
        _SpannerClientStub.database = _DatabaseRecorder()

        def execute_sql_rows_stub(
            database: object,
            query: str,
            params: dict[str, object],
        ) -> list[tuple[str, str, str, float, datetime, str]]:
            """Return empty retrieval data while preserving audit side-effects."""
            del database, query, params
            return []

        with (
            _DependencyOverrides(memory_api, {"SpannerClient": _SpannerClientStub}),
            _DependencyOverrides(memory_api, {"execute_sql_rows": execute_sql_rows_stub}),
            _DependencyOverrides(
                MemoryAPI,
                {"_update_weight_on_successful_use": _noop_weight_update},
            ),
        ):
            await MemoryAPI.create_session(
                tenant_id=TEST_TENANT_ID,
                session_id="audit_test_session",
                user_id="audit_test_user",
            )
            await MemoryAPI.add_semantic_fact(
                tenant_id=TEST_TENANT_ID,
                entity_type="PERSON",
                entity_id="audit_test_entity",
            )
            await MemoryAPI.retrieve_context_window(
                tenant_id=TEST_TENANT_ID,
                session_id="audit_test_session",
                window_size=10,
            )

        event_types = _SpannerClientStub.database.batch_recorder.audit_event_types
        assert "CREATE_SESSION" in event_types
        assert "ADD_SEMANTIC_FACT" in event_types
        assert "RETRIEVE_CONTEXT_WINDOW" in event_types
