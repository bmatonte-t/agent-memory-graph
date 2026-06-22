"""Evidence retrieval infrastructure for Phase 4 MindMap integration.

This module implements bounded path finding and neighbor-based enrichment
using GQL queries against Spanner Graph. Implements MindMap patterns:
- Deterministic shortest-path retrieval (allShortestPaths equivalent)
- Bounded neighbor enrichment with conditional filtering
- Compact serialization for token efficiency
- Explicit insufficient-evidence signals
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.cloud import spanner
    from google.cloud.spanner_gapic_v1.types import TransactionOptions

from src.db.retry import async_retry_with_backoff
from src.security.validators import validate_required_string, validate_tenant_id

logger = logging.getLogger(__name__)


class PathRetrievalError(Exception):
    """Raised when path retrieval encounters an error."""

    pass


class NeighborRetrievalError(Exception):
    """Raised when neighbor retrieval encounters an error."""

    pass


class EvidentPathFinder:
    """Bounded path finding with deterministic ordering.

    Implements Phase 4B: retrieve shortest paths between entities,
    serialize in compact format (entity->rel->entity->...).
    """

    def __init__(
        self,
        client: spanner.Client,
        max_path_length: int = 5,
        max_paths: int = 5,
        max_chars: int = 1000,
    ) -> None:
        """Initialize path finder with bounds.

        Args:
            client: Spanner client
            max_path_length: Maximum hops per path (default: 5)
            max_paths: Maximum paths returned (default: 5)
            max_chars: Maximum serialized character count (default: 1000)
        """
        self.client = client
        self.max_path_length = max_path_length
        self.max_paths = max_paths
        self.max_chars = max_chars

    async def find_paths(
        self,
        tenant_id: str,
        start_entity_id: str,
        end_entity_id: str,
        start_node_id: str | None = None,
        end_node_id: str | None = None,
    ) -> tuple[list[str], int]:
        """Find shortest paths between entities using GQL.

        Equivalent to Neo4j allShortestPaths(), but deterministic via:
        1. GQL MATCH p = shortestPath((start)-[*..N]->(end)) ordering
        2. Python sorting by path length + node count
        3. Top-k filtering (take first max_paths)

        Args:
            tenant_id: Tenant identifier for isolation
            start_entity_id: Start entity ID (from mining stage)
            end_entity_id: End entity ID (goal)
            start_node_id: Optional graph node ID to constrain start
            end_node_id: Optional graph node ID to constrain end

        Returns:
            tuple: (serialized_paths, total_chars)
                - serialized_paths: list of compact path strings
                - total_chars: total character count for token tracking

        Raises:
            PathRetrievalError: If query fails or timeout
        """
        tenant_id = validate_tenant_id(tenant_id)
        start_entity_id = validate_required_string(
            start_entity_id,
            field_name="start_entity_id",
        )
        end_entity_id = validate_required_string(
            end_entity_id,
            field_name="end_entity_id",
        )

        async def _execute_query() -> tuple[list[str], int]:
            try:
                # Build GQL query to find shortest paths
                # Constraint: max path length = max_path_length hops
                query = f"""
                    MATCH p = shortestPath(
                        (start:Node)-[*1..{self.max_path_length}]->(end:Node)
                    )
                    WHERE start.Attributes.entity_id = @start_entity
                        AND end.Attributes.entity_id = @end_entity
                        AND EXISTS (
                            SELECT 1
                            FROM MEMORY_GRAPH_TENANT_SCOPE tn
                            WHERE tn.NodeId IN (
                                SELECT n.NodeId
                                FROM MEMORY_GRAPH_NODE_SCOPE n
                                WHERE n.NodeId IN (
                                    SELECT node_id
                                    FROM UNNEST(NODES(p)) AS nodes, NODES(p) AS node_id
                                )
                            )
                            AND tn.TenantId = @tenant_id
                        )
                    RETURN NODES(p) as nodes, EDGES(p) as edges
                    ORDER BY LENGTH(p) ASC, SIZE(NODES(p)) ASC
                    LIMIT @max_paths;
                """

                from src.db.spanner_client import SpannerClient

                database = SpannerClient.get_database()
                results = []

                with database.snapshot() as snapshot:
                    params = {
                        "start_entity": start_entity_id,
                        "end_entity": end_entity_id,
                        "tenant_id": tenant_id,
                        "max_paths": self.max_paths,
                    }

                    rows = snapshot.execute_sql(query, params)

                    for row in rows:
                        nodes = row[0]  # NODES(p)
                        edges = row[1]  # EDGES(p)

                        # Serialize this path
                        serialized = await self.serialize_path(nodes, edges)
                        if serialized:
                            results.append(serialized)

                # Calculate total character count for token tracking
                total_chars = sum(len(p) for p in results)

                # Check if total exceeds max_chars budget
                if total_chars > self.max_chars:
                    logger.warning(
                        "path_retrieval_exceeded_char_budget tenant_id=%s "
                        "total_chars=%d max_chars=%d",
                        tenant_id,
                        total_chars,
                        self.max_chars,
                    )
                    # Truncate paths to fit budget
                    truncated = []
                    running_total = 0
                    for path in results:
                        if running_total + len(path) <= self.max_chars:
                            truncated.append(path)
                            running_total += len(path)
                        else:
                            break
                    results = truncated
                    total_chars = running_total

                logger.info(
                    "path_retrieval_complete tenant_id=%s path_count=%d "
                    "total_chars=%d",
                    tenant_id,
                    len(results),
                    total_chars,
                )

                return results, total_chars

            except Exception as e:
                msg = f"path_retrieval_failed: {e}"
                logger.exception(msg)
                raise PathRetrievalError(msg) from e

        try:
            return await async_retry_with_backoff(
                _execute_query,
                tenant_id=tenant_id,
                max_attempts=3,
                initial_backoff_seconds=0.25,
            )
        except Exception as e:
            raise PathRetrievalError(f"path_finding_failed_after_retries: {e}") from e

    async def serialize_path(self, path_nodes: list[dict], path_relationships: list[dict]) -> str:
        """Serialize a path to compact format.

        Format: entity->rel->entity->rel->...
        Cleans underscores, preserves deterministic order.

        Args:
            path_nodes: List of node dicts with 'id', 'entity_id' fields
            path_relationships: List of relationship dicts with 'type' field

        Returns:
            Serialized path string, e.g. "patient->has_symptom->hoarse_voice"
        """
        try:
            if not path_nodes:
                return ""

            # Extract entity identifiers from nodes
            entity_ids = []
            for node in path_nodes:
                # Try to get entity_id from node attributes
                if isinstance(node, dict):
                    entity_id = (
                        node.get("Attributes", {}).get("entity_id")
                        or node.get("entity_id")
                        or node.get("NodeId")
                    )
                else:
                    # Node might be a RowTuple from query results
                    entity_id = getattr(node, "NodeId", None) or str(node)

                if entity_id:
                    # Clean underscores to spaces
                    entity_ids.append(str(entity_id).replace("_", " "))

            if not entity_ids:
                return ""

            # Extract relationship types
            rel_types = []
            for rel in path_relationships:
                if isinstance(rel, dict):
                    rel_type = rel.get("RelType") or rel.get("type")
                else:
                    rel_type = getattr(rel, "RelType", None) or str(rel)

                if rel_type:
                    # Clean underscores to spaces
                    rel_types.append(str(rel_type).replace("_", " "))

            # Interleave: entity->rel->entity->rel->...
            # We have N entities and N-1 relationships
            if len(entity_ids) == len(rel_types) + 1:
                parts = []
                for i, entity_id in enumerate(entity_ids):
                    parts.append(entity_id)
                    if i < len(rel_types):
                        parts.append(rel_types[i])

                serialized = "->".join(parts)
                logger.debug("path_serialized serialized=%s", serialized)
                return serialized
            else:
                logger.warning(
                    "path_serialization_mismatch entities=%d relationships=%d",
                    len(entity_ids),
                    len(rel_types),
                )
                # Fallback: just concatenate entities
                return "->".join(entity_ids)

        except Exception as e:
            logger.exception("path_serialization_failed: %s", e)
            return ""


class NeighborEnricher:
    """Bounded neighbor enrichment with conditional filtering.

    Implements Phase 4C: retrieve neighbors of an entity with
    optional filtering (context flags), serialize as CSV.
    """

    def __init__(
        self,
        client: spanner.Client,
        max_direct_neighbors: int = 10,
        max_neighbors_per_entity: int = 5,
        max_chars: int = 500,
    ) -> None:
        """Initialize neighbor enricher with bounds.

        Args:
            client: Spanner client
            max_direct_neighbors: Max neighbors in 1-hop query (default: 10)
            max_neighbors_per_entity: Max after filtering (default: 5)
            max_chars: Max serialized char count (default: 500)
        """
        self.client = client
        self.max_direct_neighbors = max_direct_neighbors
        self.max_neighbors_per_entity = max_neighbors_per_entity
        self.max_chars = max_chars

    async def enrich_neighbors(
        self,
        tenant_id: str,
        entity_id: str,
        entity_node_id: str | None = None,
        context_flags: dict | None = None,
    ) -> tuple[list[str], int]:
        """Retrieve neighbors with optional conditional filtering.

        Implements MindMap's two-tier enrichment:
        1. Tier 1: Direct neighbors (1-hop, unfiltered LIMIT max_direct_neighbors)
        2. Tier 2: Conditional refinement (apply context_flags, merge back)

        Context flags (extensible):
        - skip_redundant_paths: bool - skip relationships matching pattern
        - prioritize_labels: list[str] - prefer these node labels first

        Args:
            tenant_id: Tenant identifier for isolation
            entity_id: Entity to enrich (from mining stage)
            entity_node_id: Optional graph node ID to constrain query
            context_flags: Optional dict of filtering parameters

        Returns:
            tuple: (serialized_neighbors, total_chars)
                - serialized_neighbors: list of "entity->rel->neighbor1,neighbor2,..."
                - total_chars: total char count for token tracking

        Raises:
            NeighborRetrievalError: If query fails or timeout
        """
        # TODO: Phase 4C implementation
        # 1. Build Tier 1 query: MATCH (e:Entity)-[r]->(n) WHERE ...
        # 2. Apply context_flags to WHERE clause
        # 3. Execute with retry/backoff (Phase 2 resilience)
        # 4. Limit to max_neighbors_per_entity (hard cap)
        # 5. Serialize as "entity->rel->neighbor1,neighbor2,..." (CSV)
        # 6. Validate total chars < max_chars, fail gracefully
        # 7. Return (serialized_neighbors, total_chars) tuple
        logger.warning("enrich_neighbors() not yet implemented (Phase 4C)")
        return [], 0


class EvidenceTracker:
    """Track evidence retrieval and linkage to audit events.

    Implements Phase 4D: insert ENGRAM_EVIDENCE entries, link to
    audit trail, maintain usage counts for Phase 5 confidence gating.
    """

    def __init__(self, client: spanner.Client) -> None:
        """Initialize evidence tracker.

        Args:
            client: Spanner client for ENGRAM_EVIDENCE writes
        """
        self.client = client

    async def record_evidence_retrieved(
        self,
        tenant_id: str,
        source_type: str,  # "path_based" | "neighbor_based"
        evidence_number: int,
        graph_path: str,
        serialized_form: str | None = None,
        cognitive_weight: float = 1.0,
        audit_log_ref: str | None = None,
    ) -> str:
        """Record evidence retrieval in ENGRAM_EVIDENCE (append-only).

        Creates immutable evidence entry for audit trail and Phase 5
        confidence gating (usage_count, cognitive_weight).

        Args:
            tenant_id: Tenant identifier
            source_type: "path_based" | "neighbor_based" | "hybrid"
            evidence_number: Sequential index (1-based)
            graph_path: Compact path string
            serialized_form: Natural language form (optional)
            cognitive_weight: Weight for Phase 5 gating (default: 1.0)
            audit_log_ref: Reference to AUDIT_EVENTS entry

        Returns:
            evidence_id: UUID of created ENGRAM_EVIDENCE entry

        Raises:
            ValueError: If inputs invalid
            RuntimeError: If write fails
        """
        # TODO: Phase 4D implementation
        # 1. Generate evidence_id (UUID)
        # 2. INSERT into ENGRAM_EVIDENCE with tenant_id isolation
        # 3. Set created_at = now, usage_count = 0
        # 4. Link to audit_log_ref if provided
        # 5. Return evidence_id for synthesis stage tracking
        logger.warning("record_evidence_retrieved() not yet implemented (Phase 4D)")
        return str(uuid.uuid4())

    async def link_evidence_to_synthesis(
        self,
        tenant_id: str,
        evidence_id: str,
        synthesis_id: str,
    ) -> None:
        """Link evidence usage to a synthesis result (Phase 4D audit).

        Called after synthesis completes, to record which evidence
        was actually used in the final response.

        Args:
            tenant_id: Tenant identifier
            evidence_id: ENGRAM_EVIDENCE entry ID
            synthesis_id: ID of synthesis response

        Raises:
            ValueError: If IDs invalid
            RuntimeError: If update fails
        """
        # TODO: Phase 4D implementation
        # 1. UPDATE ENGRAM_EVIDENCE SET SynthesisRefs = ARRAY_CONCAT(...)
        # 2. Increment UsageCount
        # 3. Update LastUsedTimestamp
        # NOTE: ENGRAM_EVIDENCE is append-only in schema, so this
        # is a one-time update after insert (not true UPDATE pattern)
        logger.warning("link_evidence_to_synthesis() not yet implemented (Phase 4D)")
