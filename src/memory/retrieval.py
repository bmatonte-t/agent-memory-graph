"""Evidence retrieval infrastructure for Phase 4 MindMap integration.

This module implements bounded path finding and neighbor-based enrichment
using GQL queries against Spanner Graph. Implements MindMap patterns:
- Deterministic shortest-path retrieval (allShortestPaths equivalent)
- Bounded neighbor enrichment with conditional filtering
- Compact serialization for token efficiency
- Explicit insufficient-evidence signals
"""

# ruff: noqa: S608

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from src.db.retry import async_retry_with_backoff
from src.db.spanner_client import SpannerClient
from src.integrations.google_sdk_wrappers import execute_dml, execute_sql_rows
from src.security.validators import validate_required_string, validate_tenant_id

logger = logging.getLogger(__name__)

_MIN_ROW_COLUMNS = 2


@dataclass(frozen=True)
class PathRetrievalResult:
    """Typed result returned by PathFinder.find_paths().

    Replaces the bare tuple (list[str], int) so callers have named attributes
    and static-analysis tools can verify field access.
    """

    paths: list[str]
    total_chars: int


def _is_match_query_unsupported(error: Exception) -> bool:
    """Return whether an error indicates graph MATCH is unsupported.

    Args:
        error: Exception raised while executing a query.

    Returns:
        bool: True when the backend does not support MATCH syntax.
    """
    message = str(error).lower()
    return "unexpected keyword match" in message


class PathRetrievalError(Exception):
    """Raised when path retrieval encounters an error."""


class NeighborRetrievalError(Exception):
    """Raised when neighbor retrieval encounters an error."""


class EvidentPathFinder:
    """Bounded path finding with deterministic ordering.

    Implements Phase 4B: retrieve shortest paths between entities,
    serialize in compact format (entity->rel->entity->...).
    """

    def __init__(
        self,
        client: object,
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

    async def find_paths(  # noqa: PLR0915
        self,
        tenant_id: str,
        start_entity_id: str,
        end_entity_id: str,
        start_node_id: str | None = None,
        end_node_id: str | None = None,
    ) -> PathRetrievalResult:
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
            PathRetrievalResult with paths (list of compact path strings)
            and total_chars (total character count for token tracking).

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
        del start_node_id, end_node_id

        async def _execute_query(**_: Any) -> PathRetrievalResult:
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

                database = SpannerClient.get_database()
                results: list[str] = []

                params = {
                    "start_entity": start_entity_id,
                    "end_entity": end_entity_id,
                    "tenant_id": tenant_id,
                    "max_paths": self.max_paths,
                }
                try:
                    rows = execute_sql_rows(database, query, params)
                except Exception as error:
                    if not _is_match_query_unsupported(error):
                        raise
                    logger.info(
                        "path_retrieval_match_unsupported tenant_id=%s",
                        tenant_id,
                    )
                    sql_fallback_query = """
                        SELECT e.RelType
                        FROM MemoryNode AS s
                        JOIN MemoryEdge AS e
                            ON e.SourceNodeId = s.NodeId
                            AND e.TenantId = @tenant_id
                        JOIN MemoryNode AS d
                            ON d.NodeId = e.DestNodeId
                            AND d.TenantId = @tenant_id
                        WHERE s.TenantId = @tenant_id
                          AND JSON_VALUE(s.Attributes, '$.entity_id') = @start_entity
                          AND JSON_VALUE(d.Attributes, '$.entity_id') = @end_entity
                        ORDER BY e.RelType ASC
                        LIMIT @max_paths
                    """
                    rows = execute_sql_rows(database, sql_fallback_query, params)
                    for row in rows:
                        if not row:
                            continue
                        rel_type = str(row[0]).replace("_", " ")
                        results.append(
                            f"{start_entity_id.replace('_', ' ')}"
                            f"->{rel_type}->{end_entity_id.replace('_', ' ')}"
                        )
                    total_chars = sum(len(path) for path in results)
                    return PathRetrievalResult(paths=results, total_chars=total_chars)

                for row in rows:
                    if len(row) < _MIN_ROW_COLUMNS:
                        continue

                    raw_nodes = row[0]
                    raw_edges = row[1]
                    raw_node_list = (
                        cast("list[object]", raw_nodes) if isinstance(raw_nodes, list) else []
                    )
                    raw_edge_list = (
                        cast("list[object]", raw_edges) if isinstance(raw_edges, list) else []
                    )
                    nodes = (
                        cast(
                            "list[dict[str, Any]]",
                            [node for node in raw_node_list if isinstance(node, dict)],
                        )
                        if raw_node_list
                        else []
                    )
                    edges = (
                        cast(
                            "list[dict[str, Any]]",
                            [edge for edge in raw_edge_list if isinstance(edge, dict)],
                        )
                        if raw_edge_list
                        else []
                    )

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
                    truncated: list[str] = []
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
                    "path_retrieval_complete tenant_id=%s path_count=%d total_chars=%d",
                    tenant_id,
                    len(results),
                    total_chars,
                )

                return PathRetrievalResult(paths=results, total_chars=total_chars)  # noqa: TRY300

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
            message = f"path_finding_failed_after_retries: {e}"
            raise PathRetrievalError(message) from e

    async def serialize_path(
        self,
        path_nodes: list[dict[str, Any]],
        path_relationships: list[dict[str, Any]],
    ) -> str:
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
            entity_ids: list[str] = []
            for node in path_nodes:
                # Try to get entity_id from node attributes
                attributes = node.get("Attributes")
                attributes_mapping = (
                    cast("dict[str, Any]", attributes) if isinstance(attributes, dict) else {}
                )
                entity_id = (
                    attributes_mapping.get("entity_id")
                    or node.get("entity_id")
                    or node.get("NodeId")
                )

                if entity_id:
                    # Clean underscores to spaces
                    entity_ids.append(str(entity_id).replace("_", " "))

            if not entity_ids:
                return ""

            # Extract relationship types
            rel_types: list[str] = []
            for rel in path_relationships:
                rel_type = rel.get("RelType") or rel.get("type")

                if rel_type:
                    # Clean underscores to spaces
                    rel_types.append(str(rel_type).replace("_", " "))

            # Interleave: entity->rel->entity->rel->...
            # We have N entities and N-1 relationships
            if len(entity_ids) == len(rel_types) + 1:
                parts: list[str] = []
                for i, entity_id in enumerate(entity_ids):
                    parts.append(entity_id)
                    if i < len(rel_types):
                        parts.append(rel_types[i])

                serialized = "->".join(parts)
                logger.debug("path_serialized serialized=%s", serialized)
                return serialized
            logger.warning(
                "path_serialization_mismatch entities=%d relationships=%d",
                len(entity_ids),
                len(rel_types),
            )
            # Fallback: just concatenate entities
            return "->".join(entity_ids)

        except Exception:
            logger.exception("path_serialization_failed")
            return ""


class NeighborEnricher:
    """Bounded neighbor enrichment with conditional filtering.

    Implements Phase 4C: retrieve neighbors of an entity with
    optional filtering (context flags), serialize as CSV.
    """

    def __init__(
        self,
        client: object,
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

    async def enrich_neighbors(  # noqa: PLR0915
        self,
        tenant_id: str,
        entity_id: str,
        entity_node_id: str | None = None,
        context_flags: dict[str, Any] | None = None,
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
        tenant_id = validate_tenant_id(tenant_id)
        entity_id = validate_required_string(entity_id, field_name="entity_id")
        context_flags = context_flags or {}
        del entity_node_id

        async def _execute_query(**_: Any) -> tuple[list[str], int]:  # noqa: PLR0912
            try:
                # Tier 1: Direct neighbors (1-hop) with tenant isolation
                query_tier1 = """
                    MATCH (e:Node)-[r]->(n:Node)
                    WHERE e.Attributes.entity_id = @entity_id
                      AND e.TenantId = @tenant_id
                      AND n.TenantId = @tenant_id
                    RETURN DISTINCT r.RelType as rel_type, n.Attributes.entity_id as neighbor_id
                    ORDER BY r.RelType ASC
                    LIMIT @max_direct_neighbors;
                """

                database = SpannerClient.get_database()
                neighbors_by_rel: dict[str, list[str]] = {}

                params = {
                    "entity_id": entity_id,
                    "tenant_id": tenant_id,
                    "max_direct_neighbors": self.max_direct_neighbors,
                }
                try:
                    rows = execute_sql_rows(database, query_tier1, params)
                except Exception as error:
                    if not _is_match_query_unsupported(error):
                        raise
                    logger.info(
                        "neighbor_enrichment_match_unsupported tenant_id=%s",
                        tenant_id,
                    )
                    sql_fallback_query = """
                        SELECT DISTINCT
                            e.RelType AS rel_type,
                            JSON_VALUE(n.Attributes, '$.entity_id') AS neighbor_id
                        FROM MemoryNode AS src
                        JOIN MemoryEdge AS e
                            ON e.SourceNodeId = src.NodeId
                            AND e.TenantId = @tenant_id
                        JOIN MemoryNode AS n
                            ON n.NodeId = e.DestNodeId
                            AND n.TenantId = @tenant_id
                        WHERE src.TenantId = @tenant_id
                          AND JSON_VALUE(src.Attributes, '$.entity_id') = @entity_id
                        ORDER BY rel_type ASC
                        LIMIT @max_direct_neighbors
                    """
                    rows = execute_sql_rows(database, sql_fallback_query, params)

                for row in rows:
                    if len(row) < _MIN_ROW_COLUMNS:
                        continue

                    rel_type = row[0]
                    neighbor_id = row[1]

                    if not rel_type or not neighbor_id:
                        continue

                    # Clean underscores
                    rel_type_clean = str(rel_type).replace("_", " ")
                    neighbor_id_clean = str(neighbor_id).replace("_", " ")

                    # Group neighbors by relationship type
                    if rel_type_clean not in neighbors_by_rel:
                        neighbors_by_rel[rel_type_clean] = []

                    neighbors_by_rel[rel_type_clean].append(neighbor_id_clean)

                # Tier 2: Apply context flags (conditional refinement)
                skip_redundant = context_flags.get("skip_redundant_paths", False)

                # Filter based on context flags
                filtered_neighbors: dict[str, list[str]] = {}
                for rel_type, neighbors in neighbors_by_rel.items():
                    # Skip redundant paths if flag set
                    if skip_redundant and rel_type in ["is_same_as", "has_duplicate"]:
                        continue

                    # Limit neighbors per relationship to max_neighbors_per_entity
                    filtered_neighbors[rel_type] = neighbors[: self.max_neighbors_per_entity]

                serialized_neighbors: list[str] = []
                for rel_type, neighbors in filtered_neighbors.items():
                    serialized = f"{entity_id}->{rel_type}->{','.join(neighbors)}"
                    serialized_neighbors.append(serialized)

                # Calculate total character count
                total_chars = sum(len(s) for s in serialized_neighbors)

                # Check if total exceeds max_chars budget
                if total_chars > self.max_chars:
                    logger.warning(
                        "neighbor_enrichment_exceeded_char_budget tenant_id=%s "
                        "total_chars=%d max_chars=%d",
                        tenant_id,
                        total_chars,
                        self.max_chars,
                    )
                    # Truncate to fit budget
                    truncated: list[str] = []
                    running_total = 0
                    for neighbor_str in serialized_neighbors:
                        if running_total + len(neighbor_str) <= self.max_chars:
                            truncated.append(neighbor_str)
                            running_total += len(neighbor_str)
                        else:
                            break
                    serialized_neighbors = truncated
                    total_chars = running_total

                logger.info(
                    "neighbor_enrichment_complete tenant_id=%s neighbor_count=%d total_chars=%d",
                    tenant_id,
                    len(serialized_neighbors),
                    total_chars,
                )

                return serialized_neighbors, total_chars  # noqa: TRY300

            except Exception as e:
                msg = f"neighbor_retrieval_failed: {e}"
                logger.exception(msg)
                raise NeighborRetrievalError(msg) from e

        try:
            return await async_retry_with_backoff(
                _execute_query,
                tenant_id=tenant_id,
                max_attempts=3,
                initial_backoff_seconds=0.25,
            )
        except Exception as e:
            message = f"neighbor_enrichment_failed_after_retries: {e}"
            raise NeighborRetrievalError(message) from e


class EvidenceTracker:
    """Track evidence retrieval and linkage to audit events.

    Implements Phase 4D: insert ENGRAM_EVIDENCE entries, link to
    audit trail, maintain usage counts for Phase 5 confidence gating.
    """

    def __init__(self, client: object) -> None:
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
        tenant_id = validate_tenant_id(tenant_id)
        source_type = validate_required_string(source_type, field_name="source_type")
        graph_path = validate_required_string(graph_path, field_name="graph_path")

        evidence_id = str(uuid.uuid4())

        try:
            database = SpannerClient.get_database()  # type: ignore[return-value]
            now = datetime.now(UTC)

            insert_sql = """
                INSERT INTO ENGRAM_EVIDENCE (
                    TenantId, EvidenceId, SourceType, EvidenceNumber,
                    GraphPath, SerializedForm, AccessTimestamp, UsageCount,
                    CognitiveWeight, AuditLogRef, CreatedAt
                ) VALUES (
                    @tenant_id, @evidence_id, @source_type, @evidence_number,
                    @graph_path, @serialized_form, @now, 0,
                    @cognitive_weight, @audit_log_ref, @now
                )
            """

            execute_dml(
                database,
                insert_sql,
                {
                    "tenant_id": tenant_id,
                    "evidence_id": evidence_id,
                    "source_type": source_type,
                    "evidence_number": evidence_number,
                    "graph_path": graph_path,
                    "serialized_form": serialized_form,
                    "now": now,
                    "cognitive_weight": cognitive_weight,
                    "audit_log_ref": audit_log_ref,
                },
            )

            logger.info(
                "evidence_recorded tenant_id=%s evidence_id=%s source_type=%s",
                tenant_id,
                evidence_id,
                source_type,
            )

            return evidence_id  # noqa: TRY300

        except Exception as e:
            logger.exception(
                "evidence_recording_failed tenant_id=%s source_type=%s",
                tenant_id,
                source_type,
            )
            message = f"evidence_recording_failed: {e}"
            raise RuntimeError(message) from e

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
        tenant_id = validate_tenant_id(tenant_id)
        evidence_id = validate_required_string(evidence_id, field_name="evidence_id")
        synthesis_id = validate_required_string(synthesis_id, field_name="synthesis_id")

        try:
            database = SpannerClient.get_database()  # type: ignore[return-value]
            now = datetime.now(UTC)

            # Update ENGRAM_EVIDENCE to link synthesis_id
            # Note: This is a targeted update after initial INSERT
            # (ENGRAM_EVIDENCE table is append-only at schema level,
            # but individual fields can be updated post-insert)
            update_sql = """
                UPDATE ENGRAM_EVIDENCE
                SET SynthesisRefs = ARRAY_CONCAT(
                    COALESCE(SynthesisRefs, []),
                    [@synthesis_id]
                ),
                UsageCount = UsageCount + 1,
                LastAccessedTimestamp = @now
                WHERE TenantId = @tenant_id AND EvidenceId = @evidence_id
            """

            execute_dml(
                database,
                update_sql,
                {
                    "tenant_id": tenant_id,
                    "evidence_id": evidence_id,
                    "synthesis_id": synthesis_id,
                    "now": now,
                },
            )

            logger.info(
                "evidence_linked_to_synthesis tenant_id=%s evidence_id=%s synthesis_id=%s",
                tenant_id,
                evidence_id,
                synthesis_id,
            )

        except Exception as e:
            logger.exception(
                "evidence_linking_failed tenant_id=%s evidence_id=%s",
                tenant_id,
                evidence_id,
            )
            message = f"evidence_linking_failed: {e}"
            raise RuntimeError(message) from e
