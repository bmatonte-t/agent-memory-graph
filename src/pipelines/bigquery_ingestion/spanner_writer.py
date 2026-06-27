"""Spanner writer for semantic memory ingestion with idempotent deduplication.

Writes MemoryNode and MemoryEdge entities to Spanner Graph using MERGE
statements for exact-key deduplication. Batches writes for efficiency.
"""

from __future__ import annotations

import logging

from google.cloud import spanner

logger = logging.getLogger(__name__)


class SpannerWriteError(Exception):
    """Error writing to Spanner."""

    def __init__(
        self,
        error_code: str,
        error_message: str,
        batch_size: int | None = None,
        table_name: str | None = None,
    ) -> None:
        """Initialize SpannerWriteError.

        Args:
            error_code: Machine-readable error code.
            error_message: Human-readable error message.
            batch_size: Size of batch that failed (optional).
            table_name: Table name involved in error (optional).
        """
        self.error_code = error_code
        self.error_message = error_message
        self.batch_size = batch_size
        self.table_name = table_name
        super().__init__(error_message)


class MemoryNodeBatch:
    """Batch of MemoryNode records to write to Spanner."""

    def __init__(
        self,
        tenant_id: str,
        node_id: str,
        entity_label: str,
        entity_value: str,
        cognitive_weight: float = 0.5,
        attributes: dict[str, str] | None = None,
    ) -> None:
        """Initialize MemoryNodeBatch.

        Args:
            tenant_id: Tenant identifier for isolation.
            node_id: Unique node identifier (SHA256[:16] or primary key).
            entity_label: POLE+O entity type (PERSON, OBJECT, etc.).
            entity_value: Actual entity value from BigQuery.
            cognitive_weight: Initial cognitive weight (0.0-1.0).
            attributes: JSON attributes (column_name, data_type, etc.).
        """
        self.tenant_id = tenant_id
        self.node_id = node_id
        self.entity_label = entity_label
        self.entity_value = entity_value
        self.cognitive_weight = max(0.0, min(1.0, cognitive_weight))
        self.attributes = attributes or {}

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for Spanner insert.

        Returns:
            Dictionary with Spanner column names.
        """
        return {
            "tenant_id": self.tenant_id,
            "node_id": self.node_id,
            "entity_label": self.entity_label,
            "entity_value": self.entity_value,
            "cognitive_weight": self.cognitive_weight,
            "attributes": self.attributes,
        }


class MemoryEdgeBatch:
    """Batch of MemoryEdge records to write to Spanner."""

    def __init__(
        self,
        tenant_id: str,
        source_node_id: str,
        target_node_id: str,
        relation_type: str,
        confidence: float = 0.8,
        *,
        inferred: bool = False,
    ) -> None:
        """Initialize MemoryEdgeBatch.

        Args:
            tenant_id: Tenant identifier for isolation.
            source_node_id: Source node ID.
            target_node_id: Target node ID.
            relation_type: Type of relationship (MEMBER_OF, LOCATED_AT, etc.).
            confidence: Confidence score (0.0-1.0).
            inferred: Whether relationship was inferred.
        """
        self.tenant_id = tenant_id
        self.source_node_id = source_node_id
        self.target_node_id = target_node_id
        self.relation_type = relation_type
        self.confidence = max(0.0, min(1.0, confidence))
        self.inferred = inferred

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for Spanner insert.

        Returns:
            Dictionary with Spanner column names.
        """
        return {
            "tenant_id": self.tenant_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "relation_type": self.relation_type,
            "confidence": self.confidence,
            "inferred": self.inferred,
        }


class SpannerIngestWriter:
    """Write ingested entities to Spanner Graph with idempotent dedup.

    Uses MERGE statements (upsert) for exact-key deduplication and
    batches writes for efficiency. Tracks provenance in ENGRAM_EVIDENCE.
    """

    def __init__(
        self,
        project_id: str,
        instance_id: str,
        database_id: str,
        client: spanner.Client | None = None,
    ) -> None:
        """Initialize SpannerIngestWriter.

        Args:
            project_id: GCP project ID.
            instance_id: Spanner instance ID.
            database_id: Spanner database ID.
            client: Optional pre-configured Spanner client.

        Raises:
            ValueError: If project_id, instance_id, or database_id is empty.
        """
        if not project_id or not instance_id or not database_id:
            msg = "project_id, instance_id, and database_id required"
            raise ValueError(msg)

        self.project_id = project_id
        self.instance_id = instance_id
        self.database_id = database_id
        self.client = client or spanner.Client(project=project_id)
        self.instance = self.client.instance(instance_id)
        self.database = self.instance.database(database_id)

        logger.info(
            "Initialized SpannerIngestWriter: %s/%s/%s",
            project_id,
            instance_id,
            database_id,
        )

    def write_nodes(
        self,
        tenant_id: str,
        nodes: list[MemoryNodeBatch],
        batch_size: int = 1000,
    ) -> int:
        """Write MemoryNode records to Spanner with deduplication.

        Uses MERGE to upsert on (tenant_id, node_id) key.

        Args:
            tenant_id: Tenant identifier for isolation.
            nodes: List of MemoryNodeBatch to write.
            batch_size: Max rows per batch (default 1000).

        Returns:
            Total rows written.

        Raises:
            SpannerWriteError: If write fails.
        """
        if not nodes:
            logger.debug("No nodes to write")
            return 0

        total_written = 0
        try:
            # Process in batches
            for batch_start in range(0, len(nodes), batch_size):
                batch_end = min(batch_start + batch_size, len(nodes))
                batch = nodes[batch_start:batch_end]

                with self.database.batch() as batch_conn:
                    for node in batch:
                        # MERGE for idempotent upsert
                        batch_conn.execute_update(
                            """
                            MERGE INTO MemoryNode AS target
                            USING (SELECT @tenant_id as tenant_id,
                                          @node_id as node_id) AS source
                            ON target.tenant_id = source.tenant_id
                               AND target.node_id = source.node_id
                            WHEN MATCHED THEN
                                UPDATE SET
                                    cognitive_weight = @cognitive_weight,
                                    attributes = @attributes
                            WHEN NOT MATCHED THEN
                                INSERT (
                                    tenant_id, node_id, entity_label,
                                    entity_value, cognitive_weight, attributes
                                ) VALUES (
                                    @tenant_id, @node_id, @entity_label,
                                    @entity_value, @cognitive_weight,
                                    @attributes
                                )
                            """,
                            params={
                                "tenant_id": node.tenant_id,
                                "node_id": node.node_id,
                                "entity_label": node.entity_label,
                                "entity_value": node.entity_value,
                                "cognitive_weight": node.cognitive_weight,
                                "attributes": node.attributes,
                            },
                        )

                total_written += len(batch)
                logger.debug(
                    "Wrote %d nodes in batch for tenant %s",
                    len(batch),
                    tenant_id,
                )

            logger.info(
                "Successfully wrote %d MemoryNode records for tenant %s",
                total_written,
                tenant_id,
            )
            return total_written  # noqa: TRY300

        except Exception as e:
            msg = f"Failed to write {len(nodes)} nodes for tenant {tenant_id}"
            logger.exception(msg)
            raise SpannerWriteError(
                error_code="WRITE_NODES_FAILED",
                error_message=msg,
                batch_size=batch_size,
                table_name="MemoryNode",
            ) from e

    def write_edges(
        self,
        tenant_id: str,
        edges: list[MemoryEdgeBatch],
        batch_size: int = 1000,
    ) -> int:
        """Write MemoryEdge records to Spanner with deduplication.

        Uses MERGE to upsert on (tenant_id, source_node_id, target_node_id,
        relation_type) composite key.

        Args:
            tenant_id: Tenant identifier for isolation.
            edges: List of MemoryEdgeBatch to write.
            batch_size: Max rows per batch (default 1000).

        Returns:
            Total rows written.

        Raises:
            SpannerWriteError: If write fails.
        """
        if not edges:
            logger.debug("No edges to write")
            return 0

        total_written = 0
        try:
            # Process in batches
            for batch_start in range(0, len(edges), batch_size):
                batch_end = min(batch_start + batch_size, len(edges))
                batch = edges[batch_start:batch_end]

                with self.database.batch() as batch_conn:
                    for edge in batch:
                        # MERGE for idempotent upsert
                        batch_conn.execute_update(
                            """
                            MERGE INTO MemoryEdge AS target
                            USING (SELECT @tenant_id as tenant_id,
                                          @source_node_id as source_node_id,
                                          @target_node_id as target_node_id,
                                          @relation_type as relation_type) AS s
                            ON target.tenant_id = s.tenant_id
                               AND target.source_node_id = s.source_node_id
                               AND target.target_node_id = s.target_node_id
                               AND target.relation_type = s.relation_type
                            WHEN MATCHED THEN
                                UPDATE SET confidence = @confidence,
                                          inferred = @inferred
                            WHEN NOT MATCHED THEN
                                INSERT (
                                    tenant_id, source_node_id,
                                    target_node_id, relation_type,
                                    confidence, inferred
                                ) VALUES (
                                    @tenant_id, @source_node_id,
                                    @target_node_id, @relation_type,
                                    @confidence, @inferred
                                )
                            """,
                            params={
                                "tenant_id": edge.tenant_id,
                                "source_node_id": edge.source_node_id,
                                "target_node_id": edge.target_node_id,
                                "relation_type": edge.relation_type,
                                "confidence": edge.confidence,
                                "inferred": edge.inferred,
                            },
                        )

                total_written += len(batch)
                logger.debug(
                    "Wrote %d edges in batch for tenant %s",
                    len(batch),
                    tenant_id,
                )

            logger.info(
                "Successfully wrote %d MemoryEdge records for tenant %s",
                total_written,
                tenant_id,
            )
            return total_written  # noqa: TRY300

        except Exception as e:
            msg = f"Failed to write {len(edges)} edges for tenant {tenant_id}"
            logger.exception(msg)
            raise SpannerWriteError(
                error_code="WRITE_EDGES_FAILED",
                error_message=msg,
                batch_size=batch_size,
                table_name="MemoryEdge",
            ) from e

    def record_engram_evidence(
        self,
        tenant_id: str,
        node_id: str,
        source: str,
        provenance: dict[str, str],
    ) -> None:
        """Record ENGRAM_EVIDENCE for audit trail.

        Args:
            tenant_id: Tenant identifier.
            node_id: MemoryNode ID being evidenced.
            source: Source identifier (e.g., 'bigquery_table').
            provenance: Metadata dict with project_id, dataset_id, etc.

        Raises:
            SpannerWriteError: If write fails.
        """
        try:
            with self.database.batch() as batch:
                batch.execute_update(
                    """
                    INSERT INTO ENGRAM_EVIDENCE (
                        tenant_id, node_id, source, provenance
                    ) VALUES (@tenant_id, @node_id, @source, @provenance)
                    """,
                    params={
                        "tenant_id": tenant_id,
                        "node_id": node_id,
                        "source": source,
                        "provenance": provenance,
                    },
                )

            logger.debug(
                "Recorded ENGRAM_EVIDENCE for node %s (source=%s)",
                node_id,
                source,
            )

        except Exception as e:
            msg = f"Failed to record ENGRAM_EVIDENCE for node {node_id}"
            logger.exception(msg)
            raise SpannerWriteError(
                error_code="RECORD_EVIDENCE_FAILED",
                error_message=msg,
                table_name="ENGRAM_EVIDENCE",
            ) from e
