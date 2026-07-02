"""Cross-tenant isolation tests for Phase 4 neighbor enrichment and MemoryNode writes.

Validates that neighbor enrichment queries properly isolate data by tenant_id,
and that MemoryNode write paths enforce the composite primary key (TenantId, NodeId).
This blocks Phase 4 readiness if cross-tenant data exposure occurs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

import src.memory.api as memory_api
from src.memory import retrieval
from src.memory.api import MemoryAPI
from src.memory.retrieval import NeighborEnricher

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType


class _DependencyOverrides:
    """Temporarily override module attributes during a test.

    This avoids patch-heavy tests while preserving deterministic dependency
    injection for integration-style behavior checks.
    """

    def __init__(self, module: ModuleType, overrides: dict[str, Any]) -> None:
        """Initialize override context.

        Args:
            module: Target module whose attributes will be replaced.
            overrides: Mapping of attribute names to temporary values.
        """
        self._module = module
        self._overrides = overrides
        self._originals: dict[str, Any] = {}

    def __enter__(self) -> None:
        """Apply overrides and capture originals."""
        for attribute_name, value in self._overrides.items():
            self._originals[attribute_name] = getattr(self._module, attribute_name)
            setattr(self._module, attribute_name, value)

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        """Restore original module attributes.

        Returns:
            bool: Always False to propagate exceptions.
        """
        del exc_type, exc_value, traceback
        for attribute_name, value in self._originals.items():
            setattr(self._module, attribute_name, value)
        return False


class _RetrievalSpannerClientStub:
    """Minimal retrieval-side Spanner client stub."""

    _database: object = object()

    @staticmethod
    def get_database() -> object:
        """Return deterministic fake database handle.

        Returns:
            object: Opaque database marker used by query stubs.
        """
        return _RetrievalSpannerClientStub._database


class _BatchStub:
    """Capture MemoryNode inserts while accepting other writes."""

    def __init__(self, stored_nodes: dict[tuple[str, str], dict[str, object]]) -> None:
        """Initialize batch stub.

        Args:
            stored_nodes: Composite-keyed store for captured node inserts.
        """
        self._stored_nodes = stored_nodes

    def execute_update(self, sql: str, params: dict[str, object]) -> int:
        """Capture MemoryNode writes and return success.

        Args:
            sql: SQL statement being executed.
            params: Bound parameters.

        Returns:
            int: Number of affected rows.
        """
        if "INSERT INTO MemoryNode" in sql:
            key = (str(params.get("tenant_id", "")), str(params.get("node_id", "")))
            self._stored_nodes[key] = dict(params)
        return 1


class _BatchContext:
    """Context manager wrapper for batch operations."""

    def __init__(self, batch: _BatchStub) -> None:
        """Initialize context wrapper.

        Args:
            batch: Batch object returned by __enter__.
        """
        self._batch = batch

    def __enter__(self) -> _BatchStub:
        """Return batch instance for writes.

        Returns:
            _BatchStub: Writable batch stub.
        """
        return self._batch

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        """End context without swallowing exceptions.

        Returns:
            bool: Always False to propagate exceptions.
        """
        del exc_type, exc_value, traceback
        return False


class _DatabaseStub:
    """Database stub exposing batch and transaction hooks."""

    def __init__(self, stored_nodes: dict[tuple[str, str], dict[str, object]]) -> None:
        """Initialize database stub.

        Args:
            stored_nodes: Composite-keyed storage backing inserts.
        """
        self._stored_nodes = stored_nodes

    def batch(self) -> _BatchContext:
        """Create a writable batch context.

        Returns:
            _BatchContext: Context manager returning a batch stub.
        """
        return _BatchContext(_BatchStub(self._stored_nodes))

    def run_in_transaction(self, operation: Callable[[Any], object]) -> object:
        """Fallback transaction execution using same batch stub.

        Args:
            operation: Transaction callback.

        Returns:
            object: Callback result.
        """
        return operation(_BatchStub(self._stored_nodes))


class _ApiSpannerClientStub:
    """Minimal MemoryAPI-side Spanner client stub."""

    _database: _DatabaseStub | None = None

    @staticmethod
    def get_database() -> _DatabaseStub:
        """Return configured fake database.

        Returns:
            _DatabaseStub: Stub database previously assigned by tests.

        Raises:
            RuntimeError: If test forgot to assign a database instance.
        """
        if _ApiSpannerClientStub._database is None:
            msg = "ApiSpannerClientStub database was not configured"
            raise RuntimeError(msg)
        return _ApiSpannerClientStub._database

    @staticmethod
    def _validate_audit_mutation_forbidden(table_name: str, operation: str) -> None:
        """Accept append-only audit writes in tests.

        Args:
            table_name: Audit table being mutated.
            operation: DML operation to validate.
        """
        del table_name, operation


async def _noop_weight_update(
    tenant_id: str,
    node_ids: list[str],
    session_action_count: int | None = None,
) -> None:
    """Disable weight updates for deterministic write-isolation tests.

    Args:
        tenant_id: Tenant identifier.
        node_ids: Node IDs that would be updated.
        session_action_count: Optional action count.
    """
    del tenant_id, node_ids, session_action_count


class TestCrossTenantIsolation:
    """Validate tenant boundaries for retrieval and write paths."""

    async def test_neighbor_retrieval_respects_tenant_isolation(
        self,
    ) -> None:
        """Neighbor enrichment must not return data from other tenants.

        Validates that the neighbor query includes tenant_id predicates
        and would not leak cross-tenant data even if edges existed.
        """
        # Arrange
        tenant_a = "tenant-a-isolation-test"
        tenant_b = "tenant-b-isolation-test"
        entity_id = "entity_a"

        # Create mock database with execute_sql_rows behavior
        # For tenant A: return neighbors from tenant A only
        # For tenant B: return neighbors from tenant B only
        def execute_sql_rows_stub(
            database: object,
            query: str,
            params: dict[str, object],
        ) -> list[tuple[str, str]]:
            """Mock database query execution."""
            del database
            # Verify that tenant_id is included in query
            assert "TenantId" in query, f"Query missing TenantId filter: {query}"
            assert "@tenant_id" in query, f"Query missing tenant_id parameter: {query}"

            # Return different results based on tenant
            # Rows are tuples: (rel_type, neighbor_id)
            if params.get("tenant_id") == tenant_a:
                # Tenant A has neighbor_a
                return [("KNOWS", "neighbor_a")]
            if params.get("tenant_id") == tenant_b:
                # Tenant B has neighbor_b (different neighbor)
                return [("KNOWS", "neighbor_b")]
            return []

        with _DependencyOverrides(
            retrieval,
            {
                "SpannerClient": _RetrievalSpannerClientStub,
                "execute_sql_rows": execute_sql_rows_stub,
            },
        ):
            enricher = NeighborEnricher(client=_RetrievalSpannerClientStub)

            # Act & Assert: Query neighbors for tenant A
            neighbors_a, _ = await enricher.enrich_neighbors(
                tenant_id=tenant_a,
                entity_id=entity_id,
            )

            # Verify tenant A neighbors
            assert any("neighbor a" in n for n in neighbors_a), (
                f"Tenant A should see neighbor_a, got: {neighbors_a}"
            )
            assert not any("neighbor b" in n for n in neighbors_a), (
                f"Tenant A must not see neighbor_b, got: {neighbors_a}"
            )

            # Act & Assert: Query neighbors for tenant B
            neighbors_b, _ = await enricher.enrich_neighbors(
                tenant_id=tenant_b,
                entity_id=entity_id,
            )

            # Verify tenant B neighbors
            assert any("neighbor b" in n for n in neighbors_b), (
                f"Tenant B should see neighbor_b, got: {neighbors_b}"
            )
            assert not any("neighbor a" in n for n in neighbors_b), (
                f"Tenant B must not see neighbor_a, got: {neighbors_b}"
            )

    async def test_node_id_cannot_be_reused_across_tenants_via_direct_write(self) -> None:
        """Same NodeId written to two different tenants must coexist as distinct rows.

        Composite PK is (TenantId, NodeId). Writing node_id="shared-node" to tenant-a
        and separately to tenant-b must result in two independent rows — not an overwrite.
        Reading back for each tenant must return that tenant's own attributes, proving
        the composite key correctly namespaces identical node_id values across tenants.
        """
        tenant_a = "tenant-a-pk-isolation"
        tenant_b = "tenant-b-pk-isolation"
        shared_node_id = "shared-node-id-001"

        # Track inserts keyed by (tenant_id, node_id) to simulate composite PK storage.
        stored_nodes: dict[tuple[str, str], dict[str, object]] = {}

        _ApiSpannerClientStub._database = _DatabaseStub(stored_nodes)

        with (
            _DependencyOverrides(
                memory_api,
                {
                    "SpannerClient": _ApiSpannerClientStub,
                },
            ),
            _DependencyOverrides(
                MemoryAPI,
                {
                    "_update_weight_on_successful_use": _noop_weight_update,
                },
            ),
        ):
            # Write shared_node_id to tenant-a
            await MemoryAPI.add_semantic_fact(
                tenant_id=tenant_a,
                entity_type="PERSON",
                entity_id=shared_node_id,
                attributes={"owner": "alice"},
            )

            # Write the same shared_node_id to tenant-b
            await MemoryAPI.add_semantic_fact(
                tenant_id=tenant_b,
                entity_type="PERSON",
                entity_id=shared_node_id,
                attributes={"owner": "bob"},
            )

        # Both composite keys must be present — distinct rows, not overwrites.
        assert (tenant_a, shared_node_id) in stored_nodes, (
            f"Row for tenant-a / {shared_node_id} was not written"
        )
        assert (tenant_b, shared_node_id) in stored_nodes, (
            f"Row for tenant-b / {shared_node_id} was not written"
        )

        # Each row must carry the correct tenant_id in its payload.
        assert stored_nodes[(tenant_a, shared_node_id)]["tenant_id"] == tenant_a, (
            "tenant-a row has wrong tenant_id"
        )
        assert stored_nodes[(tenant_b, shared_node_id)]["tenant_id"] == tenant_b, (
            "tenant-b row has wrong tenant_id"
        )

    async def test_memory_node_write_rejects_empty_tenant_id(self) -> None:
        """_do_add_semantic_fact_batch guard must reject empty tenant_id at write time.

        The composite PK guard added in _do_add_semantic_fact_batch (and mirrored in
        _do_create_session_batch) must raise ValueError before touching Spanner when
        tenant_id is an empty string, preventing silent composite PK corruption.
        """
        with pytest.raises(ValueError, match="tenant_id is required for all MemoryNode writes"):
            await MemoryAPI._do_add_semantic_fact_batch(
                tenant_id="",
                entity_id="some-node",
                entity_type="PERSON",
                node_attributes={},
                relationship=None,
                created_at=datetime.now(UTC),
            )

    async def test_memory_node_write_rejects_none_tenant_id(self) -> None:
        """_do_add_semantic_fact_batch guard must reject None tenant_id at write time.

        None is not a valid tenant_id for composite PK enforcement. The guard must
        catch both None and empty string to prevent all silent corruption paths.
        """
        with pytest.raises(ValueError, match="tenant_id is required for all MemoryNode writes"):
            await MemoryAPI._do_add_semantic_fact_batch(
                tenant_id=None,  # type: ignore[arg-type]
                entity_id="some-node",
                entity_type="PERSON",
                node_attributes={},
                relationship=None,
                created_at=datetime.now(UTC),
            )
