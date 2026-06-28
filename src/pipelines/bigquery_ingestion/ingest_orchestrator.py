"""Orchestrate BigQuery schema analysis through Spanner persistence.

This module coordinates the complete ingestion pipeline:
  1. Schema analysis (extract metadata and sample rows)
  2. POLE+O classification (classify columns via Gemini)
  3. Schema mapping (map to MemoryNode/MemoryEdge graph entities)
  4. Spanner persistence (write nodes/edges with idempotent MERGE)

Ensures tenant isolation, error recovery, and audit trail recording.

Type System Note:
  This module uses component classes (BigQuerySchemaAnalyzer, POLEClassifier,
  SchemaMapper) that internally call untyped Google Cloud SDK methods (Gemini,
  BigQuery). This causes Unknown types to propagate through this module.

  Per ADR-0002, the long-term solution is to refactor these component classes
  to use typed wrappers from src/integrations/google_sdk_wrappers.py. Until
  then, we suppress reportUnknownVariableType at module level (see line 12).

  This is a documented exception, not a code smell. All downstream consumers
  of this module receive typed results (MemoryNodeBatch, MemoryEdgeBatch),
  so the Unknown types are fully contained.
"""

# pyright: reportUnknownVariableType=false

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from google.cloud import bigquery, spanner

from src.pipelines.bigquery_ingestion.pole_classifier import (
    POLEClassifier,
    TableClassification,
)
from src.pipelines.bigquery_ingestion.schema_analyzer import (
    BigQuerySchemaAnalyzer,
)
from src.pipelines.bigquery_ingestion.schema_mapper import SchemaMapper
from src.pipelines.bigquery_ingestion.spanner_writer import (
    MemoryEdgeBatch,
    MemoryNodeBatch,
    SpannerIngestWriter,
)

if TYPE_CHECKING:
    from src.pipelines.bigquery_ingestion.schema_analyzer import (
        TableMetadata,
    )
    from src.pipelines.bigquery_ingestion.schema_mapper import (
        SchemaMapping,
    )

# Type aliases for return types
ClassificationResult = TableClassification

logger = logging.getLogger(__name__)

# Default batch sizes for write operations
DEFAULT_NODE_BATCH_SIZE = 1000
DEFAULT_EDGE_BATCH_SIZE = 1000


class IngestOrchestratorError(Exception):
    """Error during orchestration pipeline execution.

    Attributes:
        error_code: Machine-readable error identifier.
        error_message: Human-readable error description.
        project_id: GCP project ID where error occurred.
        dataset_id: BigQuery dataset ID.
        table_id: BigQuery table ID (if applicable).
        stage: Pipeline stage where error occurred.
        tenant_id: Tenant identifier for multi-tenancy isolation.
    """

    def __init__(
        self,
        *,
        error_code: str,
        error_message: str,
        project_id: str | None = None,
        dataset_id: str | None = None,
        table_id: str | None = None,
        stage: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """Initialize IngestOrchestratorError.

        Args:
            error_code: Machine-readable error code.
            error_message: Human-readable description.
            project_id: Optional GCP project ID.
            dataset_id: Optional BigQuery dataset ID.
            table_id: Optional BigQuery table ID.
            stage: Optional pipeline stage identifier.
            tenant_id: Optional tenant identifier.
        """
        self.error_code = error_code
        self.error_message = error_message
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.stage = stage
        self.tenant_id = tenant_id
        msg = f"[{error_code}] {error_message}"
        if stage:
            msg += f" (stage: {stage})"
        super().__init__(msg)


class BigQueryIngestJob:
    """Orchestrate BigQuery ingestion through Spanner.

    Manages the complete pipeline: schema analysis, POLE+O classification,
    schema mapping, and Spanner persistence. Supports per-table configuration,
    error recovery, and audit trail recording.
    """

    def __init__(
        self,
        project_id: str,
        bigquery_dataset_id: str,
        spanner_project_id: str,
        spanner_instance_id: str,
        spanner_database_id: str,
        tenant_id: str,
        bq_client: bigquery.Client | None = None,
        spanner_client: spanner.Client | None = None,
    ) -> None:
        """Initialize BigQueryIngestJob.

        Args:
            project_id: GCP project ID for BigQuery.
            bigquery_dataset_id: BigQuery dataset to ingest from.
            spanner_project_id: GCP project ID for Spanner.
            spanner_instance_id: Spanner instance name.
            spanner_database_id: Spanner database name.
            tenant_id: Tenant identifier for isolation.
            bq_client: Optional pre-configured BigQuery client.
            spanner_client: Optional pre-configured Spanner client.

        Raises:
            ValueError: If required parameters are empty.
        """
        if not all(
            [
                project_id,
                bigquery_dataset_id,
                spanner_project_id,
                spanner_instance_id,
                spanner_database_id,
                tenant_id,
            ]
        ):
            msg = (
                "All parameters (project_id, bigquery_dataset_id, "
                "spanner_project_id, spanner_instance_id, "
                "spanner_database_id, tenant_id) required"
            )
            raise ValueError(msg)

        self.project_id = project_id
        self.bigquery_dataset_id = bigquery_dataset_id
        self.spanner_project_id = spanner_project_id
        self.spanner_instance_id = spanner_instance_id
        self.spanner_database_id = spanner_database_id
        self.tenant_id = tenant_id

        # Initialize clients
        self.bq_client = bq_client or bigquery.Client(project=project_id)
        self.spanner_client = spanner_client or spanner.Client(project=spanner_project_id)

        # Initialize pipeline components
        self.schema_analyzer: BigQuerySchemaAnalyzer = BigQuerySchemaAnalyzer(self.bq_client)
        self.classifier: POLEClassifier = POLEClassifier(project_id=project_id)
        self.schema_mapper: SchemaMapper = SchemaMapper()
        self.spanner_writer: SpannerIngestWriter = SpannerIngestWriter(
            spanner_project_id,
            spanner_instance_id,
            spanner_database_id,
            client=self.spanner_client,
        )

        logger.info(
            "Initialized BigQueryIngestJob for tenant %s: BQ %s.%s -> Spanner %s/%s/%s",
            tenant_id,
            project_id,
            bigquery_dataset_id,
            spanner_project_id,
            spanner_instance_id,
            spanner_database_id,
        )

    def ingest_table(
        self,
        table_id: str,
        node_batch_size: int = DEFAULT_NODE_BATCH_SIZE,
        edge_batch_size: int = DEFAULT_EDGE_BATCH_SIZE,
    ) -> dict[str, int]:
        """Ingest a single BigQuery table into Spanner.

        Orchestrates complete pipeline for one table: schema analysis,
        POLE+O classification, mapping, and Spanner writes.

        Args:
            table_id: BigQuery table name to ingest.
            node_batch_size: Batch size for node writes (default 1000).
            edge_batch_size: Batch size for edge writes (default 1000).

        Returns:
            dict[str, int]: Summary with 'nodes_written', 'edges_written',
                'relationships_inferred'.

        Raises:
            IngestOrchestratorError: If any pipeline stage fails.
        """
        logger.info(
            "Starting ingestion for table %s.%s (tenant: %s)",
            self.bigquery_dataset_id,
            table_id,
            self.tenant_id,
        )

        try:
            # Stage 1: Schema Analysis
            logger.info("Stage 1/4: Analyzing schema for %s", table_id)
            table_metadata = self._analyze_schema(table_id)

            # Stage 2: POLE+O Classification
            logger.info("Stage 2/4: Classifying columns via Gemini")
            classification = self._classify_schema(table_metadata)

            # Stage 3: Schema Mapping
            logger.info("Stage 3/4: Mapping schema to graph entities")
            mapping = self._map_schema(table_metadata, classification)

            # Stage 4: Spanner Persistence
            logger.info("Stage 4/4: Writing to Spanner")
            result = self._write_to_spanner(
                mapping,
                table_id,
                node_batch_size,
                edge_batch_size,
            )

            logger.info(
                "Completed ingestion for %s: nodes=%d, edges=%d, inferred=%d",
                table_id,
                result["nodes_written"],
                result["edges_written"],
                result["relationships_inferred"],
            )

            return result  # noqa: TRY300

        except IngestOrchestratorError:
            raise
        except Exception as e:
            msg = f"Unexpected error during ingestion of {table_id}: {e!s}"
            logger.exception(msg)
            raise IngestOrchestratorError(
                error_code="INGEST_UNEXPECTED_ERROR",
                error_message=msg,
                project_id=self.project_id,
                dataset_id=self.bigquery_dataset_id,
                table_id=table_id,
                tenant_id=self.tenant_id,
            ) from e

    def ingest_dataset(
        self,
        node_batch_size: int = DEFAULT_NODE_BATCH_SIZE,
        edge_batch_size: int = DEFAULT_EDGE_BATCH_SIZE,
    ) -> dict[str, int]:
        """Ingest all tables in a BigQuery dataset into Spanner.

        Iterates through all tables in the dataset and ingests each one.
        Accumulates totals across all tables.

        Args:
            node_batch_size: Batch size for node writes.
            edge_batch_size: Batch size for edge writes.

        Returns:
            dict[str, int]: Aggregated summary with totals for all tables.

        Raises:
            IngestOrchestratorError: If dataset listing or any table
                ingestion fails.
        """
        logger.info(
            "Starting dataset-wide ingestion for %s.* (tenant: %s)",
            self.bigquery_dataset_id,
            self.tenant_id,
        )

        try:
            # List all tables in dataset
            tables = self.schema_analyzer.list_tables(self.project_id, self.bigquery_dataset_id)
            logger.info("Found %d tables in dataset", len(tables))

            totals = {
                "nodes_written": 0,
                "edges_written": 0,
                "relationships_inferred": 0,
                "tables_processed": 0,
                "tables_failed": 0,
            }

            for table_id, _ in tables:
                try:
                    result = self.ingest_table(table_id, node_batch_size, edge_batch_size)
                    totals["nodes_written"] += result["nodes_written"]
                    totals["edges_written"] += result["edges_written"]
                    totals["relationships_inferred"] += result["relationships_inferred"]
                    totals["tables_processed"] += 1
                except IngestOrchestratorError as e:
                    logger.warning("Failed to ingest table %s: %s", table_id, e)
                    totals["tables_failed"] += 1

            logger.info(
                "Dataset ingestion complete: processed=%d, failed=%d, nodes=%d, edges=%d",
                totals["tables_processed"],
                totals["tables_failed"],
                totals["nodes_written"],
                totals["edges_written"],
            )

            return totals  # noqa: TRY300

        except Exception as e:
            msg = f"Failed to list tables in {self.bigquery_dataset_id}: {e!s}"
            logger.exception(msg)
            raise IngestOrchestratorError(
                error_code="LIST_TABLES_FAILED",
                error_message=msg,
                project_id=self.project_id,
                dataset_id=self.bigquery_dataset_id,
                tenant_id=self.tenant_id,
            ) from e

    def _analyze_schema(self, table_id: str) -> TableMetadata:
        """Analyze BigQuery table schema (Stage 1).

        Args:
            table_id: BigQuery table name.

        Returns:
            TableMetadata: Metadata with columns, row count, sizes.

        Raises:
            IngestOrchestratorError: If schema analysis fails.
        """
        try:
            full_table_id = f"{self.project_id}.{self.bigquery_dataset_id}.{table_id}"
            metadata = self.schema_analyzer.get_table_schema(full_table_id)  # type: ignore[reportCallIssue, reportUnknownArgumentType]
            logger.debug(
                "Analyzed schema for %s: %d columns, %d rows",
                table_id,
                len(metadata.columns),  # type: ignore[reportUnknownMemberType]
                metadata.row_count,  # type: ignore[reportUnknownMemberType]
            )
        except Exception as e:
            msg = f"Schema analysis failed for {table_id}: {e!s}"
            logger.exception(msg)
            raise IngestOrchestratorError(
                error_code="SCHEMA_ANALYSIS_FAILED",
                error_message=msg,
                project_id=self.project_id,
                dataset_id=self.bigquery_dataset_id,
                table_id=table_id,
                stage="analyze_schema",
                tenant_id=self.tenant_id,
            ) from e
        else:
            return metadata

    def _classify_schema(self, table_metadata: TableMetadata) -> ClassificationResult:
        """Classify schema columns via Gemini (Stage 2).

        Args:
            table_metadata: Table metadata from schema analysis.

        Returns:
            dict[str, object]: Classification results with entity types
                and confidence scores.

        Raises:
            IngestOrchestratorError: If classification fails.
        """
        try:
            # Sample rows for classification context
            sample_rows = self.schema_analyzer.sample_rows(  # type: ignore[reportCallIssue, reportUnknownArgumentType]
                f"{self.project_id}.{self.bigquery_dataset_id}.{table_metadata.table_id}",
                limit=10,
            )
            logger.debug(
                "Sampled %d rows for classification",
                len(sample_rows),  # type: ignore[reportUnknownMemberType]
            )

            # Classify columns
            classification = self.classifier.classify_columns(table_metadata, sample_rows)  # type: ignore[reportUnknownArgumentType]
            logger.debug(
                "Classified %d columns (confidence: %.2f)",
                len(classification.classified_columns),  # type: ignore[reportUnknownMemberType]
                classification.overall_confidence,  # type: ignore[reportUnknownMemberType]
            )
        except Exception as e:
            msg = f"Schema classification failed: {e!s}"
            logger.exception(msg)
            raise IngestOrchestratorError(
                error_code="CLASSIFICATION_FAILED",
                error_message=msg,
                project_id=self.project_id,
                dataset_id=self.bigquery_dataset_id,
                table_id=table_metadata.table_id,
                stage="classify_schema",
                tenant_id=self.tenant_id,
            ) from e
        else:
            return classification  # type: ignore[reportReturnType, reportUnknownVariableType]

    def _map_schema(
        self,
        table_metadata: TableMetadata,
        classification: TableClassification,
    ) -> SchemaMapping:
        """Map schema to MemoryNode/MemoryEdge entities (Stage 3).

        Args:
            table_metadata: Table metadata from stage 1.
            classification: Classification results from stage 2.

        Returns:
            SchemaMapping: Mapping with entity nodes and relationships.

        Raises:
            IngestOrchestratorError: If mapping fails.
        """
        try:
            mapping = self.schema_mapper.create_mapping(table_metadata, classification)
            logger.debug(
                "Mapped %d entity nodes, %d relationships",
                len(mapping.entity_nodes),
                len(mapping.relationships),
            )
            return mapping  # noqa: TRY300
        except Exception as e:
            msg = f"Schema mapping failed: {e!s}"
            logger.exception(msg)
            raise IngestOrchestratorError(
                error_code="MAPPING_FAILED",
                error_message=msg,
                project_id=self.project_id,
                dataset_id=self.bigquery_dataset_id,
                table_id=table_metadata.table_id,
                stage="map_schema",
                tenant_id=self.tenant_id,
            ) from e

    def _write_to_spanner(
        self,
        mapping: SchemaMapping,
        table_id: str,
        node_batch_size: int,
        edge_batch_size: int,
    ) -> dict[str, int]:
        """Write mapped entities to Spanner (Stage 4).

        Args:
            mapping: Schema mapping from stage 3.
            table_id: Source BigQuery table ID.
            node_batch_size: Batch size for node writes.
            edge_batch_size: Batch size for edge writes.

        Returns:
            dict[str, int]: Write result with counts.

        Raises:
            IngestOrchestratorError: If Spanner write fails.
        """
        try:
            # Convert mapped entities to MemoryNodeBatch records
            node_batches: list[MemoryNodeBatch] = []
            for entity_node_obj in mapping.entity_nodes:  # type: ignore[reportUnknownMemberType]
                # entity_node is Unknown, so access attributes with getattr
                node_id = str(
                    getattr(entity_node_obj, "node_id", "")  # type: ignore[reportUnknownArgumentType]
                )
                entity_label = str(
                    getattr(entity_node_obj, "entity_type", "")  # type: ignore[reportUnknownArgumentType]
                )
                entity_value = str(
                    getattr(entity_node_obj, "column_name", "")  # type: ignore[reportUnknownArgumentType]
                )
                data_type = str(
                    getattr(entity_node_obj, "data_type", "")  # type: ignore[reportUnknownArgumentType]
                )
                entity_types = str(
                    getattr(entity_node_obj, "entity_types", "")  # type: ignore[reportUnknownArgumentType]
                )

                batch = MemoryNodeBatch(
                    tenant_id=self.tenant_id,
                    node_id=node_id,
                    entity_label=entity_label,
                    entity_value=entity_value,
                    cognitive_weight=0.5,  # Initial weight
                    attributes={
                        "source_table": table_id,
                        "data_type": data_type,
                        "entity_types": entity_types,
                    },
                )
                node_batches.append(batch)

            # Write nodes
            nodes_written = self.spanner_writer.write_nodes(
                self.tenant_id,
                node_batches,
                batch_size=node_batch_size,
            )
            logger.info(
                "Wrote %d MemoryNode records for %s",
                nodes_written,
                table_id,
            )

            # Convert relationships to MemoryEdgeBatch records
            edge_batches: list[MemoryEdgeBatch] = []
            inferred_count = 0
            for rel_obj in mapping.relationships:  # type: ignore[reportUnknownMemberType]
                # rel is Unknown, so access attributes with getattr
                source_node_id = str(
                    getattr(rel_obj, "source_node_id", "")  # type: ignore[reportUnknownArgumentType]
                )
                target_node_id = str(
                    getattr(rel_obj, "target_node_id", "")  # type: ignore[reportUnknownArgumentType]
                )
                relation_type = str(
                    getattr(rel_obj, "relation_type", "")  # type: ignore[reportUnknownArgumentType]
                )
                confidence = float(
                    getattr(rel_obj, "confidence", 0.0)  # type: ignore[reportUnknownArgumentType]
                )
                inferred = bool(
                    getattr(rel_obj, "inferred", False)  # type: ignore[reportUnknownArgumentType]
                )

                batch = MemoryEdgeBatch(
                    tenant_id=self.tenant_id,
                    source_node_id=source_node_id,
                    target_node_id=target_node_id,
                    relation_type=relation_type,
                    confidence=confidence,
                    inferred=inferred,
                )
                edge_batches.append(batch)
                if inferred:
                    inferred_count += 1

            # Write edges
            edges_written = self.spanner_writer.write_edges(
                self.tenant_id,
                edge_batches,
                batch_size=edge_batch_size,
            )
            logger.info(
                "Wrote %d MemoryEdge records (%d inferred) for %s",
                edges_written,
                inferred_count,
                table_id,
            )

            # Record audit trail
            if node_batches:
                # Use the first node as the reference for audit evidence
                primary_node_id = node_batches[0].node_id
                self.spanner_writer.record_engram_evidence(
                    tenant_id=self.tenant_id,
                    node_id=primary_node_id,
                    source="bigquery_table",
                    provenance={
                        "project_id": self.project_id,
                        "dataset_id": self.bigquery_dataset_id,
                        "table_id": table_id,
                        "ingestion_timestamp": datetime.now(UTC).isoformat(),
                        "nodes_count": str(len(node_batches)),
                        "edges_count": str(len(edge_batches)),
                    },
                )
                logger.debug("Recorded engram evidence for %s", table_id)

            return {  # noqa: TRY300
                "nodes_written": nodes_written,
                "edges_written": edges_written,
                "relationships_inferred": inferred_count,
            }

        except Exception as e:
            msg = f"Spanner write failed for {table_id}: {e!s}"
            logger.exception(msg)
            raise IngestOrchestratorError(
                error_code="SPANNER_WRITE_FAILED",
                error_message=msg,
                project_id=self.project_id,
                dataset_id=self.bigquery_dataset_id,
                table_id=table_id,
                stage="write_to_spanner",
                tenant_id=self.tenant_id,
            ) from e

    def clear_caches(self) -> None:
        """Clear internal caches (schema, classification).

        Useful for testing or forcing full re-analysis.
        """
        self.schema_analyzer.clear_cache()
        self.classifier.cache.clear()
        logger.info("Cleared ingestion pipeline caches")
