"""BigQuery schema analyzer for ingestion pipeline.

Extracts table metadata and schema information from BigQuery to understand
table structure for POLE+O entity classification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)


class ColumnSchema(BaseModel):
    """Schema definition for a BigQuery column."""

    name: str
    field_type: str
    mode: str = "NULLABLE"
    description: str | None = None


class TableMetadata(BaseModel):
    """Metadata for a BigQuery table."""

    project_id: str
    dataset_id: str
    table_id: str
    full_table_id: str
    columns: list[ColumnSchema]
    row_count: int | None = None
    table_size_bytes: int | None = None
    created_time: str | None = None
    modified_time: str | None = None


@dataclass(frozen=True)
class BigQueryMetadataFetchError(Exception):
    """Exception raised when BigQuery metadata fetch fails."""

    error_code: str
    error_message: str
    project_id: str | None = None
    dataset_id: str | None = None
    table_id: str | None = None


class BigQuerySchemaAnalyzer:
    """Analyzes BigQuery schemas for entity ingestion.

    Fetches table metadata, column types, and row counts to support
    POLE+O entity classification and schema mapping.
    """

    def __init__(self, bq_client: bigquery.Client | None = None) -> None:
        """Initialize schema analyzer.

        Args:
            bq_client: BigQuery client instance. If None, creates default.
        """
        self.client = bq_client or bigquery.Client()
        self._metadata_cache: dict[str, TableMetadata] = {}

    def list_tables(
        self,
        project_id: str,
        dataset_id: str,
    ) -> list[tuple[str, int | None]]:
        """List all tables in a BigQuery dataset.

        Args:
            project_id: GCP project ID.
            dataset_id: BigQuery dataset ID.

        Returns:
            List of (table_id, row_count) tuples.

        Raises:
            BigQueryMetadataFetchError: If fetch fails.
        """
        try:
            dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
            tables = cast("Iterable[Any]", self.client.list_tables(dataset_ref))

            result: list[tuple[str, int | None]] = []
            for raw_table in tables:
                table = raw_table
                # Attempt to get row count
                row_count = None
                try:
                    full_table = self.client.get_table(table.reference)
                    row_count = full_table.num_rows
                except GoogleAPICallError as error:
                    logger.warning(
                        "Failed to get row count for %s.%s: %s",
                        dataset_id,
                        table.table_id,
                        str(error),
                    )

                result.append((table.table_id, row_count))

            logger.info(
                "Listed %d tables in %s.%s",
                len(result),
                project_id,
                dataset_id,
            )

        except Exception as e:
            msg = f"Failed to list tables in {dataset_id}: {e!s}"
            logger.exception(msg)
            raise BigQueryMetadataFetchError(
                error_code="LIST_TABLES_FAILED",
                error_message=msg,
                project_id=project_id,
                dataset_id=dataset_id,
            ) from e
        else:
            return result

    def get_table_schema(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
    ) -> TableMetadata:
        """Get BigQuery table schema.

        Args:
            project_id: GCP project ID.
            dataset_id: BigQuery dataset ID.
            table_id: BigQuery table ID.

        Returns:
            TableMetadata with column definitions.

        Raises:
            BigQueryMetadataFetchError: If schema fetch fails.
        """
        cache_key = f"{project_id}.{dataset_id}.{table_id}"
        if cache_key in self._metadata_cache:
            logger.debug("Using cached schema for %s", cache_key)
            return self._metadata_cache[cache_key]

        try:
            table_ref = self.client.get_table(f"{project_id}.{dataset_id}.{table_id}")

            # Extract column information
            columns: list[ColumnSchema] = []
            for raw_field in cast("Iterable[Any]", table_ref.schema):
                field = raw_field
                col_schema = ColumnSchema(
                    name=field.name,
                    field_type=field.field_type,
                    mode=field.mode,
                    description=field.description,
                )
                columns.append(col_schema)

            # Create metadata object
            metadata = TableMetadata(
                project_id=project_id,
                dataset_id=dataset_id,
                table_id=table_id,
                full_table_id=f"{project_id}.{dataset_id}.{table_id}",
                columns=columns,
                row_count=table_ref.num_rows,
                table_size_bytes=table_ref.num_bytes,
                created_time=(table_ref.created.isoformat() if table_ref.created else None),
                modified_time=(table_ref.modified.isoformat() if table_ref.modified else None),
            )

            # Cache result
            self._metadata_cache[cache_key] = metadata
            logger.info(
                "Analyzed schema for %s: %d columns",
                cache_key,
                len(columns),
            )

        except Exception as e:
            msg = f"Failed to get schema for {project_id}.{dataset_id}.{table_id}: {e!s}"
            logger.exception(msg)
            raise BigQueryMetadataFetchError(
                error_code="GET_SCHEMA_FAILED",
                error_message=msg,
                project_id=project_id,
                dataset_id=dataset_id,
                table_id=table_id,
            ) from e
        else:
            return metadata

    def sample_rows(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        """Sample rows from a table for POLE+O classification.

        Args:
            project_id: GCP project ID.
            dataset_id: BigQuery dataset ID.
            table_id: BigQuery table ID.
            limit: Maximum number of rows to return.

        Returns:
            List of row dictionaries.

        Raises:
            BigQueryMetadataFetchError: If sampling fails.
        """
        try:
            query = (
                f"SELECT * FROM `{project_id}.{dataset_id}.{table_id}` "  # noqa: S608
                f"LIMIT {limit}"
            )
            job_config = bigquery.QueryJobConfig(use_query_cache=True)
            query_job = self.client.query(query, job_config=job_config)

            query_rows = cast("Iterable[Any]", query_job.result())
            rows = [dict(row.items()) for row in query_rows]

            logger.info(
                "Sampled %d rows from %s.%s.%s",
                len(rows),
                project_id,
                dataset_id,
                table_id,
            )

        except Exception as e:
            msg = f"Failed to sample rows from {project_id}.{dataset_id}.{table_id}: {e!s}"
            logger.exception(msg)
            raise BigQueryMetadataFetchError(
                error_code="SAMPLE_ROWS_FAILED",
                error_message=msg,
                project_id=project_id,
                dataset_id=dataset_id,
                table_id=table_id,
            ) from e
        else:
            return rows

    def clear_cache(self) -> None:
        """Clear metadata cache."""
        self._metadata_cache.clear()
        logger.debug("Cleared schema metadata cache")
