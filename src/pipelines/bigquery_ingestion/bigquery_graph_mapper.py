"""BigQuery Graph Mapper - creates GQL-queryable views for lazy querying.

Generates BigQuery views that represent the ingested graph structure for
analytics queries with seconds-level latency (no data movement from Spanner).
"""

from __future__ import annotations

import logging

from google.cloud import bigquery

logger = logging.getLogger(__name__)


class BigQueryGraphMapperError(Exception):
    """Error creating BigQuery graph views."""

    def __init__(
        self,
        error_code: str,
        error_message: str,
        dataset_id: str | None = None,
        view_name: str | None = None,
    ) -> None:
        """Initialize BigQueryGraphMapperError.

        Args:
            error_code: Machine-readable error code.
            error_message: Human-readable error message.
            dataset_id: BigQuery dataset ID (optional).
            view_name: View name involved in error (optional).
        """
        self.error_code = error_code
        self.error_message = error_message
        self.dataset_id = dataset_id
        self.view_name = view_name
        super().__init__(error_message)


class BigQueryGraphMapper:
    """Create BigQuery views for lazy querying of ingested graph data.

    Views provide seconds-level latency access to graph without moving
    data from Spanner. Supports POLE+O entity queries and relationship
    traversal.
    """

    def __init__(
        self,
        project_id: str,
        dataset_id: str,
        client: bigquery.Client | None = None,
    ) -> None:
        """Initialize BigQueryGraphMapper.

        Args:
            project_id: GCP project ID.
            dataset_id: BigQuery dataset for views (must exist).
            client: Optional pre-configured BigQuery client.

        Raises:
            ValueError: If project_id or dataset_id is empty.
        """
        if not project_id or not dataset_id:
            msg = "project_id and dataset_id required"
            raise ValueError(msg)

        self.project_id = project_id
        self.dataset_id = dataset_id
        self.client = client or bigquery.Client(project=project_id)

        logger.info(
            "Initialized BigQueryGraphMapper: %s.%s",
            project_id,
            dataset_id,
        )

    def create_entity_view(
        self,
        source_table: str,
        tenant_id: str,
        entity_types: list[str] | None = None,
        min_cognitive_weight: float = 0.3,
    ) -> str:
        """Create view for POLE+O entities above cognitive threshold.

        Args:
            source_table: Full Spanner memory table reference
                (project.dataset.table) or mapped BigQuery table.
            tenant_id: Tenant to filter for.
            entity_types: Optional list to filter (e.g., [PERSON, OBJECT]).
            min_cognitive_weight: Cognitive weight threshold (default 0.3).

        Returns:
            View name created (e.g., vw_entities_tenant_abc).

        Raises:
            BigQueryGraphMapperError: If view creation fails.
        """
        view_name = f"vw_entities_{tenant_id}".lower()
        entity_filter = ""
        if entity_types:
            # Validate entity types to prevent injection
            valid_types = {
                "PERSON",
                "OBJECT",
                "LOCATION",
                "EVENT",
                "ORGANIZATION",
                "TEMPORAL",
                "IDENTIFIER",
                "CATEGORY",
                "NUMERIC",
                "RELATIONSHIP",
            }
            filtered_types = [t for t in entity_types if t in valid_types]
            if filtered_types:
                placeholders = ",".join([f"'{t}'" for t in filtered_types])
                entity_filter = f"AND entity_label IN ({placeholders})"

        sql = (
            f"CREATE OR REPLACE VIEW `{self.project_id}.{self.dataset_id}."  # noqa: S608
            f"{view_name}` AS "
            f"SELECT node_id, entity_label, entity_value, cognitive_weight, "
            f"attributes FROM `{source_table}` "
            f"WHERE tenant_id = '{tenant_id}' "
            f"AND cognitive_weight >= {min_cognitive_weight} "
            f"{entity_filter} ORDER BY cognitive_weight DESC"
        )

        try:
            job = self.client.query(sql)
            job.result()

            logger.info(
                "Created entity view %s for tenant %s",
                view_name,
                tenant_id,
            )
            return view_name  # noqa: TRY300

        except Exception as e:
            msg = f"Failed to create entity view for tenant {tenant_id}"
            logger.exception(msg)
            raise BigQueryGraphMapperError(
                error_code="CREATE_ENTITY_VIEW_FAILED",
                error_message=msg,
                dataset_id=self.dataset_id,
                view_name=view_name,
            ) from e

    def create_relationship_view(
        self,
        source_edge_table: str,
        source_node_table: str,
        tenant_id: str,
        relation_types: list[str] | None = None,
        min_confidence: float = 0.7,
    ) -> str:
        """Create view for entity relationships with nodes.

        Joins edges with source/target nodes for full context.

        Args:
            source_edge_table: Full Spanner/BigQuery edge table reference.
            source_node_table: Full Spanner/BigQuery node table reference.
            tenant_id: Tenant to filter for.
            relation_types: Optional list to filter (e.g., [MEMBER_OF]).
            min_confidence: Confidence threshold (default 0.7).

        Returns:
            View name created (e.g., vw_relationships_tenant_abc).

        Raises:
            BigQueryGraphMapperError: If view creation fails.
        """
        view_name = f"vw_relationships_{tenant_id}".lower()
        relation_filter = ""
        if relation_types:
            # Validate relation types to prevent injection
            valid_rels = {
                "MEMBER_OF",
                "LOCATED_AT",
                "OWNS",
                "USES",
                "REFERS_TO",
                "CONNECTS",
                "DEPENDS_ON",
            }
            filtered_rels = [t for t in relation_types if t in valid_rels]
            if filtered_rels:
                placeholders = ",".join([f"'{t}'" for t in filtered_rels])
                relation_filter = f"AND e.relation_type IN ({placeholders})"

        sql = (
            f"CREATE OR REPLACE VIEW `{self.project_id}.{self.dataset_id}."  # noqa: S608
            f"{view_name}` AS "
            f"SELECT e.source_node_id, e.target_node_id, "
            f"e.relation_type, e.confidence, e.inferred, "
            f"src.entity_label as source_entity_type, "
            f"src.entity_value as source_entity_value, "
            f"tgt.entity_label as target_entity_type, "
            f"tgt.entity_value as target_entity_value "
            f"FROM `{source_edge_table}` e "
            f"JOIN `{source_node_table}` src "
            f"ON e.tenant_id = src.tenant_id "
            f"AND e.source_node_id = src.node_id "
            f"JOIN `{source_node_table}` tgt "
            f"ON e.tenant_id = tgt.tenant_id "
            f"AND e.target_node_id = tgt.node_id "
            f"WHERE e.tenant_id = '{tenant_id}' "
            f"AND e.confidence >= {min_confidence} "
            f"{relation_filter} ORDER BY e.confidence DESC"
        )

        try:
            job = self.client.query(sql)
            job.result()

            logger.info(
                "Created relationship view %s for tenant %s",
                view_name,
                tenant_id,
            )
            return view_name  # noqa: TRY300

        except Exception as e:
            msg = f"Failed to create relationship view for tenant {tenant_id}"
            logger.exception(msg)
            raise BigQueryGraphMapperError(
                error_code="CREATE_RELATIONSHIP_VIEW_FAILED",
                error_message=msg,
                dataset_id=self.dataset_id,
                view_name=view_name,
            ) from e

    def create_paths_view(
        self,
        source_edge_table: str,
        source_node_table: str,
        tenant_id: str,
        max_depth: int = 3,
    ) -> str:
        """Create view for graph traversal paths (BFS).

        Supports up to max_depth hops for pattern discovery.

        Args:
            source_edge_table: Full Spanner/BigQuery edge table reference.
            source_node_table: Full Spanner/BigQuery node table reference.
            tenant_id: Tenant to filter for.
            max_depth: Maximum hops to traverse (default 3).

        Returns:
            View name created (e.g., vw_paths_tenant_abc).

        Raises:
            BigQueryGraphMapperError: If view creation fails.
        """
        view_name = f"vw_paths_{tenant_id}".lower()

        # For BigQuery, we use a recursive CTE to traverse paths
        sql = (
            f"CREATE OR REPLACE VIEW "  # noqa: S608
            f"`{self.project_id}.{self.dataset_id}.{view_name}` AS "
            f"WITH RECURSIVE paths AS ("
            f"SELECT tenant_id, node_id, [node_id] as path, "
            f"0 as depth FROM `{source_node_table}` "
            f"WHERE tenant_id = '{tenant_id}' "
            f"UNION ALL "
            f"SELECT e.tenant_id, tgt.node_id, "
            f"ARRAY_CONCAT(p.path, [tgt.node_id]) as path, "
            f"p.depth + 1 FROM paths p "
            f"JOIN `{source_edge_table}` e "
            f"ON p.tenant_id = e.tenant_id "
            f"AND p.node_id = e.source_node_id "
            f"JOIN `{source_node_table}` tgt "
            f"ON e.tenant_id = tgt.tenant_id "
            f"AND e.target_node_id = tgt.node_id "
            f"WHERE p.depth < {max_depth} "
            f"AND NOT (tgt.node_id IN UNNEST(p.path))"
            f") SELECT tenant_id, node_id, path, depth, "
            f"ARRAY_LENGTH(path) as path_length FROM paths "
            f"WHERE depth > 0"
        )

        try:
            job = self.client.query(sql)
            job.result()

            logger.info(
                "Created paths view %s for tenant %s (max_depth=%d)",
                view_name,
                tenant_id,
                max_depth,
            )
            return view_name  # noqa: TRY300

        except Exception as e:
            msg = f"Failed to create paths view for tenant {tenant_id}"
            logger.exception(msg)
            raise BigQueryGraphMapperError(
                error_code="CREATE_PATHS_VIEW_FAILED",
                error_message=msg,
                dataset_id=self.dataset_id,
                view_name=view_name,
            ) from e

    def drop_view(self, view_name: str) -> None:
        """Drop a created view.

        Args:
            view_name: Name of view to drop.

        Raises:
            BigQueryGraphMapperError: If drop fails.
        """
        try:
            self.client.delete_table(
                f"{self.project_id}.{self.dataset_id}.{view_name}",
                not_found_ok=True,
            )
            logger.info("Dropped view %s", view_name)

        except Exception as e:
            msg = f"Failed to drop view {view_name}"
            logger.exception(msg)
            raise BigQueryGraphMapperError(
                error_code="DROP_VIEW_FAILED",
                error_message=msg,
                dataset_id=self.dataset_id,
                view_name=view_name,
            ) from e
