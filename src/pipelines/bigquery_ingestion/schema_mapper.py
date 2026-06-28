"""Schema mapper for BigQuery to Spanner graph transformation.

Maps BigQuery table structure and POLE+O classifications to Spanner
MemoryNode and MemoryEdge structure.
"""

from __future__ import annotations

import hashlib
import logging
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.pipelines.bigquery_ingestion.pole_classifier import (
        TableClassification,
    )
    from src.pipelines.bigquery_ingestion.schema_analyzer import (
        TableMetadata,
    )

logger = logging.getLogger(__name__)


class EntityIDStrategy(StrEnum):
    """Strategy for generating entity IDs."""

    PRIMARY_KEY = "primary_key"
    HASH = "hash"
    COMPOSITE = "composite"


class AttributeMapping(BaseModel):
    """Maps a BigQuery column to a Spanner node attribute."""

    column_name: str
    attribute_name: str
    data_type: str
    include_in_node: bool = True


class RelationshipMapping(BaseModel):
    """Defines a relationship between entities."""

    source_column: str
    target_column: str
    relation_type: str
    is_inferred: bool = False


class EntityNodeMapping(BaseModel):
    """Mapping for a single entity in the graph."""

    column_name: str
    entity_types: list[str]
    id_strategy: EntityIDStrategy
    primary_key_column: str | None = None
    attributes: list[AttributeMapping]


class SchemaMapping(BaseModel):
    """Complete schema mapping from BigQuery to Spanner."""

    source_table: str
    entity_nodes: list[EntityNodeMapping]
    relationships: list[RelationshipMapping]
    cognitive_weight_init: float = Field(
        0.5, ge=0.0, le=1.0, description="Initial cognitive weight"
    )


class SchemaMapper:
    """Maps BigQuery schema to Spanner graph structure.

    Bridges BigQuery table structure and POLE+O classifications to
    Spanner MemoryNode/MemoryEdge architecture.
    """

    def __init__(self) -> None:
        """Initialize schema mapper."""
        self.mappings: dict[str, SchemaMapping] = {}

    def create_mapping(
        self,
        table_metadata: TableMetadata,
        classification: TableClassification,
        primary_key_column: str | None = None,
    ) -> SchemaMapping:
        """Create schema mapping from table metadata and classification.

        Args:
            table_metadata: BigQuery table schema.
            classification: POLE+O classification result.
            primary_key_column: Primary key column (if known).

        Returns:
            SchemaMapping with entity and relationship definitions.
        """
        table_id = f"{table_metadata.dataset_id}.{table_metadata.table_id}"
        logger.info("Creating schema mapping for %s", table_id)

        # Build entity node mappings
        entity_nodes: list[EntityNodeMapping] = []
        for classified_col in classification.classified_columns:
            # Find column schema
            col_schema = next(
                (c for c in table_metadata.columns if c.name == classified_col.column_name),
                None,
            )
            if not col_schema:
                continue

            # Determine ID strategy
            id_strategy = EntityIDStrategy.HASH
            if primary_key_column == classified_col.column_name:
                id_strategy = EntityIDStrategy.PRIMARY_KEY

            # Build attribute mappings
            attributes = [
                AttributeMapping(
                    column_name=classified_col.column_name,
                    attribute_name=classified_col.column_name,
                    data_type=classified_col.column_type,
                    include_in_node=True,
                )
            ]

            # Create entity node mapping
            entity_node = EntityNodeMapping(
                column_name=classified_col.column_name,
                entity_types=classified_col.entity_types,
                id_strategy=id_strategy,
                primary_key_column=(
                    primary_key_column if id_strategy == EntityIDStrategy.PRIMARY_KEY else None
                ),
                attributes=attributes,
            )
            entity_nodes.append(entity_node)

        # Infer relationships (placeholder - can be enhanced)
        relationships = self._infer_relationships(table_metadata, classification)

        # Create schema mapping
        mapping = SchemaMapping(
            source_table=table_id,
            entity_nodes=entity_nodes,
            relationships=relationships,
            cognitive_weight_init=0.5,
        )

        # Cache mapping
        self.mappings[table_id] = mapping

        logger.info(
            "Created mapping for %s: %d entities, %d relationships",
            table_id,
            len(entity_nodes),
            len(relationships),
        )
        return mapping

    def _infer_relationships(
        self,
        table_metadata: TableMetadata,
        classification: TableClassification,
    ) -> list[RelationshipMapping]:
        """Infer relationships between columns.

        Basic heuristics:
        - If column ends with _id, it might reference another entity
        - PERSON columns might relate to ORGANIZATION columns
        - OBJECT columns might relate to LOCATION or EVENT columns

        Args:
            table_metadata: Table schema.
            classification: POLE+O classification.

        Returns:
            List of inferred relationships.
        """
        relationships: list[RelationshipMapping] = []

        # Get classified columns by entity type
        person_cols = [c for c in classification.classified_columns if "PERSON" in c.entity_types]
        object_cols = [c for c in classification.classified_columns if "OBJECT" in c.entity_types]
        location_cols = [
            c for c in classification.classified_columns if "LOCATION" in c.entity_types
        ]
        org_cols = [
            c for c in classification.classified_columns if "ORGANIZATION" in c.entity_types
        ]

        # Heuristic 1: ID columns might reference other entities
        for col in classification.classified_columns:
            if "IDENTIFIER" in col.entity_types and col.column_name.endswith("_id"):
                # Look for related entity
                base_name = col.column_name[:-3]  # Remove _id suffix
                related_cols = [
                    c for c in classification.classified_columns if base_name in c.column_name
                ]
                if related_cols and related_cols[0] != col:
                    rel = RelationshipMapping(
                        source_column=col.column_name,
                        target_column=related_cols[0].column_name,
                        relation_type="REFERENCES",
                        is_inferred=True,
                    )
                    relationships.append(rel)

        # Heuristic 2: PERSON might belong to ORGANIZATION
        if person_cols and org_cols:
            rel = RelationshipMapping(
                source_column=person_cols[0].column_name,
                target_column=org_cols[0].column_name,
                relation_type="MEMBER_OF",
                is_inferred=True,
            )
            relationships.append(rel)

        # Heuristic 3: OBJECT might be at LOCATION
        if object_cols and location_cols:
            rel = RelationshipMapping(
                source_column=object_cols[0].column_name,
                target_column=location_cols[0].column_name,
                relation_type="LOCATED_AT",
                is_inferred=True,
            )
            relationships.append(rel)

        logger.debug(
            "Inferred %d relationships for %s.%s",
            len(relationships),
            table_metadata.dataset_id,
            table_metadata.table_id,
        )
        return relationships

    def get_entity_id(
        self,
        _mapping: SchemaMapping,
        row_data: dict[str, object],
        entity_mapping: EntityNodeMapping,
    ) -> str:
        """Generate entity ID for a row based on ID strategy.

        Args:
            mapping: Schema mapping.
            row_data: Row data from BigQuery.
            entity_mapping: Entity mapping definition.

        Returns:
            Generated entity ID.
        """
        if (
            entity_mapping.id_strategy == EntityIDStrategy.PRIMARY_KEY
            and entity_mapping.primary_key_column
        ):
            value = row_data.get(entity_mapping.primary_key_column, "")
            return str(value)

        # Hash strategy: hash the entity's column value
        value = row_data.get(entity_mapping.column_name, "")
        value_str = str(value)
        entity_hash = hashlib.sha256(value_str.encode()).hexdigest()[:16]
        return f"{entity_mapping.column_name}_{entity_hash}"

    def clear_mappings(self) -> None:
        """Clear cached mappings."""
        self.mappings.clear()
        logger.debug("Cleared schema mappings cache")
