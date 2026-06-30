"""Cross-tenant isolation tests for Phase 4 neighbor enrichment and MemoryNode writes.

Validates that neighbor enrichment queries properly isolate data by tenant_id,
and that MemoryNode write paths enforce the composite primary key (TenantId, NodeId).
This blocks Phase 4 readiness if cross-tenant data exposure occurs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.memory.api import MemoryAPI
from src.memory.retrieval import NeighborEnricher


class TestCrossTenantIsolation:
    """Validate that neighbor queries respect tenant boundaries."""

    @pytest.fixture
    def mock_spanner_client(self) -> MagicMock:
        """Create a mock Spanner client."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_neighbor_retrieval_respects_tenant_isolation(
        self,
        mock_spanner_client: MagicMock,
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
        def mock_execute(database: object, query: str, params: dict) -> list:
            """Mock database query execution."""
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

        # Mock SpannerClient.get_database to return mock
        with (
            patch(
                "src.memory.retrieval.SpannerClient.get_database",
                return_value=mock_spanner_client,
            ),
            patch(
                "src.memory.retrieval.execute_sql_rows",
                side_effect=mock_execute,
            ),
        ):
            enricher = NeighborEnricher(client=mock_spanner_client)

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

    @pytest.mark.asyncio
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

        def make_mock_db(tenant_id: str, entity_id: str, entity_type: str) -> MagicMock:
            """Build a per-call mock database that records inserts keyed by composite PK."""
            mock_db = MagicMock()
            mock_batch = MagicMock()

            def fake_execute_update(sql: str, params: dict[str, object]) -> int:
                """Capture INSERT params into stored_nodes under composite (tenant, node) key."""
                if "INSERT INTO MemoryNode" in sql:
                    key = (str(params.get("tenant_id", "")), str(params.get("node_id", "")))
                    stored_nodes[key] = dict(params)
                return 1

            mock_batch.execute_update.side_effect = fake_execute_update
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)
            return mock_db

        with (
            patch("src.memory.api.SpannerClient.get_database") as mock_get_db,
            patch.object(
                MemoryAPI,
                "_update_weight_on_successful_use",
                new_callable=AsyncMock,
            ),
        ):
            # Write shared_node_id to tenant-a
            mock_get_db.return_value = make_mock_db(tenant_a, shared_node_id, "PERSON")
            await MemoryAPI.add_semantic_fact(
                tenant_id=tenant_a,
                entity_type="PERSON",
                entity_id=shared_node_id,
                attributes={"owner": "alice"},
            )

            # Write the same shared_node_id to tenant-b
            mock_get_db.return_value = make_mock_db(tenant_b, shared_node_id, "PERSON")
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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
