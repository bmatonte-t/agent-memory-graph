"""Cross-tenant isolation tests for Phase 4 neighbor enrichment.

Validates that neighbor enrichment queries properly isolate data by tenant_id.
This blocks Phase 4 readiness if cross-tenant data exposure occurs.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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

    def test_spanner_client_write_node_rejects_empty_tenant_id(self) -> None:
        """SpannerClient.write_node must reject empty or None tenant_id.

        Composite PK enforcement: every MemoryNode write must include a non-empty
        TenantId. Passing an empty or None tenant_id would silently corrupt the
        composite primary key (TenantId, NodeId), allowing cross-tenant collisions.
        """
        from src.db.spanner_client import SpannerClient

        with pytest.raises(ValueError, match="tenant_id is required for all writes"):
            SpannerClient.write_node(
                tenant_id="",
                node_id="some-node",
                memory_tier="SEMANTIC",
                label="PERSON",
                weight=0.5,
            )

    def test_spanner_client_write_node_rejects_none_tenant_id(self) -> None:
        """SpannerClient.write_node must reject None tenant_id explicitly.

        None is not a valid tenant_id for composite PK enforcement. The guard must
        check both None and empty string to prevent all silent corruption paths.
        """
        from src.db.spanner_client import SpannerClient

        with pytest.raises(ValueError, match="tenant_id is required for all writes"):
            SpannerClient.write_node(
                tenant_id=None,  # type: ignore[arg-type]
                node_id="some-node",
                memory_tier="SEMANTIC",
                label="PERSON",
                weight=0.5,
            )
