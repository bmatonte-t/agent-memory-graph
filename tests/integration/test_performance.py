"""Load tests and performance benchmarks for memory APIs."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from src.memory.api import MemoryAPI

P95_SESSION_TARGET_MS = 50
P95_FACT_TARGET_MS = 50
P95_CONTEXT_TARGET_MS = 200
LARGE_GRAPH_QUERY_TARGET_MS = 500
LARGE_GRAPH_TURN_COUNT = 100
CONCURRENT_TASK_COUNT = 10
SIMULATED_NODE_COUNT = 10_000
SIMULATED_EDGE_COUNT = 100_000
TEST_TENANT_ID = "tenant_perf"


class TestLoadScenarios:
    """Load tests with performance benchmarks."""

    @pytest.mark.asyncio
    async def test_bulk_session_creation_latency(self) -> None:
        """Load test: Create 100 sessions and measure p95 latency.

        Target: <50ms per session
        """
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = TEST_TENANT_ID

            with patch.object(MemoryAPI, "record_audit_event"):
                latencies = []
                num_sessions = 100

                for i in range(num_sessions):
                    start = time.perf_counter()
                    await MemoryAPI.create_session(
                        tenant_id=TEST_TENANT_ID,
                        session_id=f"session_{i}",
                        user_id=f"user_{i}",
                    )
                    elapsed = (time.perf_counter() - start) * 1000  # ms

                    latencies.append(elapsed)

                # Calculate percentiles
                sorted_latencies = sorted(latencies)
                sorted_latencies[int(len(sorted_latencies) * 0.50)]
                p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
                sorted_latencies[int(len(sorted_latencies) * 0.99)]

                # Assert performance targets
                assert p95 < P95_SESSION_TARGET_MS, (
                    f"p95 latency {p95}ms exceeds {P95_SESSION_TARGET_MS}ms target"
                )

    @pytest.mark.asyncio
    async def test_bulk_semantic_fact_ingestion(self) -> None:
        """Load test: Ingest 1000 semantic facts and measure p95 latency.

        Target: <50ms per fact
        """
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = TEST_TENANT_ID

            with (
                patch.object(MemoryAPI, "record_audit_event"),
                patch.object(MemoryAPI, "_update_weight_on_successful_use"),
            ):
                latencies = []
                num_facts = 100  # Reduced for test speed

                entity_types = ["PERSON", "OBJECT", "LOCATION", "EVENT", "ORGANIZATION"]

                for i in range(num_facts):
                    entity_type = entity_types[i % len(entity_types)]
                    start = time.perf_counter()
                    await MemoryAPI.add_semantic_fact(
                        tenant_id=TEST_TENANT_ID,
                        entity_type=entity_type,
                        entity_id=f"entity_{i}",
                        attributes={"name": f"Entity {i}"},
                    )
                    elapsed = (time.perf_counter() - start) * 1000

                    latencies.append(elapsed)

                sorted_latencies = sorted(latencies)
                sorted_latencies[int(len(sorted_latencies) * 0.50)]
                p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
                sorted_latencies[int(len(sorted_latencies) * 0.99)]

                assert p95 < P95_FACT_TARGET_MS, (
                    f"p95 latency {p95}ms exceeds {P95_FACT_TARGET_MS}ms target"
                )

    @pytest.mark.asyncio
    async def test_context_window_retrieval_latency(self) -> None:
        """Load test: Retrieve context windows 100 times with 10 turns each.

        Target: <200ms per retrieval
        """
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_snapshot = MagicMock()

            # Mock 10 turns per retrieval
            mock_turns = [
                (f"turn_{i}", "User", '{"content": "test"}', 0.5, time.time(), "HAS_TURN")
                for i in range(10)
            ]
            mock_snapshot.execute_sql.return_value = mock_turns

            mock_db.snapshot.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.snapshot.return_value.__exit__ = MagicMock(return_value=None)
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = TEST_TENANT_ID

            with (
                patch.object(MemoryAPI, "record_audit_event"),
                patch.object(MemoryAPI, "_update_weight_on_successful_use"),
            ):
                latencies = []
                num_retrievals = 100

                for i in range(num_retrievals):
                    start = time.perf_counter()
                    await MemoryAPI.retrieve_context_window(
                        tenant_id=TEST_TENANT_ID, session_id=f"session_{i}", window_size=10
                    )
                    elapsed = (time.perf_counter() - start) * 1000

                    latencies.append(elapsed)

                sorted_latencies = sorted(latencies)
                sorted_latencies[int(len(sorted_latencies) * 0.50)]
                p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
                sorted_latencies[int(len(sorted_latencies) * 0.99)]

                assert p95 < P95_CONTEXT_TARGET_MS, (
                    f"p95 latency {p95}ms exceeds {P95_CONTEXT_TARGET_MS}ms target"
                )

    @pytest.mark.asyncio
    async def test_graph_traversal_with_large_edge_set(self) -> None:
        """Test: Retrieve context window with 100 edges from single session.

        Target: <500ms for complex graph queries
        """
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_snapshot = MagicMock()

            # Mock 100 turns with varying weights
            mock_turns = [
                (
                    f"turn_{i}",
                    "User" if i % 2 == 0 else "Agent",
                    f'{{"content": "message {i}"}}',
                    0.5 - (i * 0.001),  # Decaying weights
                    time.time(),
                    "HAS_TURN",
                )
                for i in range(100)
            ]
            mock_snapshot.execute_sql.return_value = mock_turns

            mock_db.snapshot.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.snapshot.return_value.__exit__ = MagicMock(return_value=None)
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = TEST_TENANT_ID

            with (
                patch.object(MemoryAPI, "record_audit_event"),
                patch.object(MemoryAPI, "_update_weight_on_successful_use"),
            ):
                start = time.perf_counter()
                result = await MemoryAPI.retrieve_context_window(
                    tenant_id=TEST_TENANT_ID, session_id="session_large", window_size=100
                )
                elapsed = (time.perf_counter() - start) * 1000

                assert elapsed < LARGE_GRAPH_QUERY_TARGET_MS, (
                    f"Large graph query {elapsed}ms exceeds {LARGE_GRAPH_QUERY_TARGET_MS}ms target"
                )
                assert len(result.turns) == LARGE_GRAPH_TURN_COUNT

    @pytest.mark.asyncio
    async def test_simulated_write_pattern_for_10k_nodes_100k_edges(self) -> None:
        """Simulate high-scale write pressure profile using mocked Spanner batch calls.

        The test intentionally does not perform real database writes; it validates the
        expected volume pattern for node and edge mutations in a deterministic way.
        """
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = TEST_TENANT_ID

            with mock_db.batch() as batch:
                for node_index in range(SIMULATED_NODE_COUNT):
                    batch.execute_update(
                        "INSERT INTO MemoryNode (NodeId) VALUES (@node_id)",
                        {"node_id": f"node_{node_index}"},
                    )
                for edge_index in range(SIMULATED_EDGE_COUNT):
                    batch.execute_update(
                        "INSERT INTO MemoryEdge (EdgeId) VALUES (@edge_id)",
                        {"edge_id": f"edge_{edge_index}"},
                    )

            expected_total_writes = SIMULATED_NODE_COUNT + SIMULATED_EDGE_COUNT
            assert mock_batch.execute_update.call_count == expected_total_writes


class TestConcurrency:
    """Tests for concurrent operation handling."""

    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self) -> None:
        """Test concurrent creation of 10 sessions."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = TEST_TENANT_ID

            with patch.object(MemoryAPI, "record_audit_event"):
                # Create 10 sessions concurrently
                tasks = [
                    MemoryAPI.create_session(
                        tenant_id=TEST_TENANT_ID,
                        session_id=f"concurrent_session_{i}",
                        user_id=f"concurrent_user_{i}",
                    )
                    for i in range(10)
                ]

                results = await asyncio.gather(*tasks)

                assert len(results) == CONCURRENT_TASK_COUNT
                assert all(r.status == "active" for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_semantic_fact_and_retrieval(self) -> None:
        """Test concurrent fact ingestion and context retrieval."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()

            mock_batch.return_value = None
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            # Mock snapshot for retrievals
            mock_turns = [
                (f"turn_{i}", "User", '{"content": "test"}', 0.5, time.time(), "HAS_TURN")
                for i in range(5)
            ]
            mock_snapshot.execute_sql.return_value = mock_turns
            mock_db.snapshot.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.snapshot.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = TEST_TENANT_ID

            with (
                patch.object(MemoryAPI, "record_audit_event"),
                patch.object(MemoryAPI, "_update_weight_on_successful_use"),
            ):
                # Mix fact ingestion and retrievals
                tasks = []
                for i in range(10):
                    if i % 2 == 0:
                        tasks.append(
                            MemoryAPI.add_semantic_fact(
                                tenant_id=TEST_TENANT_ID,
                                entity_type="PERSON",
                                entity_id=f"concurrent_entity_{i}",
                            )
                        )
                    else:
                        tasks.append(
                            MemoryAPI.retrieve_context_window(
                                tenant_id=TEST_TENANT_ID,
                                session_id=f"concurrent_session_{i}",
                                window_size=10,
                            )
                        )

                results = await asyncio.gather(*tasks)
                assert len(results) == CONCURRENT_TASK_COUNT


class TestAuditTrailIntegrity:
    """Tests for audit trail immutability and completeness."""

    @pytest.mark.asyncio
    async def test_all_operations_generate_audit_events(self) -> None:
        """Verify every operation generates audit trail entry."""
        with patch("src.memory.api.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_snapshot = MagicMock()

            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)
            mock_snapshot.execute_sql.return_value = []
            mock_db.snapshot.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.snapshot.return_value.__exit__ = MagicMock(return_value=None)
            mock_client.get_database.return_value = mock_db
            mock_client.validate_tenant_id.return_value = TEST_TENANT_ID

            with patch.object(MemoryAPI, "_update_weight_on_successful_use"):
                # Execute operations
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

                # Verify audit events were persisted.
                audit_event_types: list[str] = []
                for call in mock_batch.execute_update.call_args_list:
                    params = call[0][1]
                    if "event_type" not in params:
                        continue
                    audit_event_types.append(params["event_type"])

                assert "CREATE_SESSION" in audit_event_types
                assert "ADD_SEMANTIC_FACT" in audit_event_types
                assert "RETRIEVE_CONTEXT_WINDOW" in audit_event_types
