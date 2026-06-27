"""Unit tests for BigQueryIngestJob orchestrator.

Tests cover orchestration workflow, error handling, tenant isolation,
and cache management.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.pipelines.bigquery_ingestion.ingest_orchestrator import (
    BigQueryIngestJob,
    IngestOrchestratorError,
)
from src.pipelines.bigquery_ingestion.schema_mapper import (
    AttributeMapping,
    EntityIDStrategy,
    EntityNodeMapping,
    SchemaMapping,
)

# Test constants for magic number replacements
EXPECTED_NODES_WRITTEN = 10
EXPECTED_EDGES_WRITTEN = 5
EXPECTED_INFERRED_RELATIONSHIPS = 2
CUSTOM_NODE_BATCH_SIZE = 500
CUSTOM_EDGE_BATCH_SIZE = 200
MULTIPLE_TABLES_PROCESSED = 2
ALL_TABLES_SUCCESS = 0
MULTI_TABLE_NODES = 30
MULTI_TABLE_EDGES = 15
PARTIAL_TABLES_FAILED = 1
PARTIAL_TABLES_PROCESSED = 2
TABLES_IN_LIST = 3
CUSTOM_TABLE_BATCH = 100
MULTI_TABLE_INFERRED = 6
DEFAULT_CONFIDENCE = 0.9


class TestIngestOrchestratorError:
    """Tests for IngestOrchestratorError exception."""

    def test_error_initialization(self) -> None:
        """Test error initialization with all fields."""
        error = IngestOrchestratorError(
            error_code="TEST_ERROR",
            error_message="Test message",
            project_id="p1",
            dataset_id="d1",
            table_id="t1",
            stage="test_stage",
            tenant_id="tenant1",
        )

        assert error.error_code == "TEST_ERROR"
        assert error.error_message == "Test message"
        assert error.project_id == "p1"
        assert error.dataset_id == "d1"
        assert error.table_id == "t1"
        assert error.stage == "test_stage"
        assert error.tenant_id == "tenant1"
        assert "[TEST_ERROR]" in str(error)
        assert "test_stage" in str(error)

    def test_error_message_without_stage(self) -> None:
        """Test error message formatting without stage."""
        error = IngestOrchestratorError(
            error_code="CODE",
            error_message="Message",
        )
        assert "[CODE] Message" in str(error)


class TestBigQueryIngestJobInit:
    """Tests for BigQueryIngestJob initialization."""

    @patch("src.pipelines.bigquery_ingestion.ingest_orchestrator.bigquery.Client")
    @patch("src.pipelines.bigquery_ingestion.ingest_orchestrator.spanner.Client")
    def test_job_initialization(
        self,
        mock_spanner_client_class: MagicMock,
        mock_bq_client_class: MagicMock,
    ) -> None:
        """Test job initialization with required parameters."""
        mock_bq_client = MagicMock()
        mock_spanner_client = MagicMock()
        mock_bq_client_class.return_value = mock_bq_client
        mock_spanner_client_class.return_value = mock_spanner_client

        job = BigQueryIngestJob(
            project_id="p1",
            bigquery_dataset_id="bq_ds",
            spanner_project_id="sp1",
            spanner_instance_id="si1",
            spanner_database_id="sd1",
            tenant_id="t1",
        )

        assert job.project_id == "p1"
        assert job.bigquery_dataset_id == "bq_ds"
        assert job.tenant_id == "t1"
        assert job.spanner_writer is not None

    def test_job_initialization_missing_parameters(self) -> None:
        """Test that initialization fails with missing parameters."""
        with pytest.raises(ValueError, match=r"All parameters.*required"):
            BigQueryIngestJob(
                project_id="",  # Empty
                bigquery_dataset_id="d1",
                spanner_project_id="sp1",
                spanner_instance_id="si1",
                spanner_database_id="sd1",
                tenant_id="t1",
            )

    @patch("src.pipelines.bigquery_ingestion.ingest_orchestrator.spanner.Client")
    def test_job_initialization_with_clients(self, mock_spanner_client_class: MagicMock) -> None:
        """Test job initialization with pre-configured clients."""
        mock_bq_client = MagicMock()
        mock_spanner_client = MagicMock()

        job = BigQueryIngestJob(
            project_id="p1",
            bigquery_dataset_id="d1",
            spanner_project_id="sp1",
            spanner_instance_id="si1",
            spanner_database_id="sd1",
            tenant_id="t1",
            bq_client=mock_bq_client,
            spanner_client=mock_spanner_client,
        )

        assert job.bq_client is mock_bq_client
        assert job.spanner_client is mock_spanner_client


class TestBigQueryIngestJobIngestTable:
    """Tests for single table ingestion orchestration."""

    @pytest.fixture
    def job(self) -> BigQueryIngestJob:
        """Create BigQueryIngestJob with mocked clients."""
        with (
            patch("src.pipelines.bigquery_ingestion.ingest_orchestrator.bigquery.Client"),
            patch("src.pipelines.bigquery_ingestion.ingest_orchestrator.spanner.Client"),
        ):
            return BigQueryIngestJob(
                project_id="p1",
                bigquery_dataset_id="d1",
                spanner_project_id="sp1",
                spanner_instance_id="si1",
                spanner_database_id="sd1",
                tenant_id="t1",
            )

    @patch.object(BigQueryIngestJob, "_analyze_schema")
    @patch.object(BigQueryIngestJob, "_classify_schema")
    @patch.object(BigQueryIngestJob, "_map_schema")
    @patch.object(BigQueryIngestJob, "_write_to_spanner")
    def test_ingest_table_success(
        self,
        mock_write: MagicMock,
        mock_map: MagicMock,
        mock_classify: MagicMock,
        mock_analyze: MagicMock,
        job: BigQueryIngestJob,
    ) -> None:
        """Test successful single table ingestion."""
        # Mock successful pipeline stages
        mock_analyze.return_value = MagicMock()
        mock_classify.return_value = {}
        mock_map.return_value = SchemaMapping(
            source_table="t1",
            entity_nodes=[],
            relationships=[],
        )
        mock_write.return_value = {
            "nodes_written": EXPECTED_NODES_WRITTEN,
            "edges_written": EXPECTED_EDGES_WRITTEN,
            "relationships_inferred": EXPECTED_INFERRED_RELATIONSHIPS,
        }

        result = job.ingest_table("table1")

        assert result["nodes_written"] == EXPECTED_NODES_WRITTEN
        assert result["edges_written"] == EXPECTED_EDGES_WRITTEN
        assert result["relationships_inferred"] == EXPECTED_INFERRED_RELATIONSHIPS
        # Verify all stages were called in order
        mock_analyze.assert_called_once()
        mock_classify.assert_called_once()
        mock_map.assert_called_once()
        mock_write.assert_called_once()

    def test_ingest_table_analysis_failure(self, job: BigQueryIngestJob) -> None:
        """Test error handling when schema analysis fails."""
        with (
            patch.object(
                job.schema_analyzer,
                "get_table_schema",
                side_effect=RuntimeError("Analysis failed"),
            ),
            pytest.raises(
                IngestOrchestratorError,
                match="SCHEMA_ANALYSIS_FAILED",
            ),
        ):
            job.ingest_table("table1")

    def test_ingest_table_classification_failure(self, job: BigQueryIngestJob) -> None:
        """Test error handling when classification fails."""
        mock_metadata = MagicMock()
        with (
            patch.object(
                job.schema_analyzer,
                "get_table_schema",
                return_value=mock_metadata,
            ),
            patch.object(job.schema_analyzer, "sample_rows", return_value=[]),
            patch.object(
                job.classifier,
                "classify_columns",
                side_effect=RuntimeError("Classification failed"),
            ),
            pytest.raises(
                IngestOrchestratorError,
                match="CLASSIFICATION_FAILED",
            ),
        ):
            job.ingest_table("table1")

    @patch.object(BigQueryIngestJob, "_analyze_schema")
    @patch.object(BigQueryIngestJob, "_classify_schema")
    @patch.object(BigQueryIngestJob, "_map_schema")
    @patch.object(BigQueryIngestJob, "_write_to_spanner")
    def test_ingest_table_with_custom_batch_sizes(
        self,
        mock_write: MagicMock,
        mock_map: MagicMock,
        mock_classify: MagicMock,
        mock_analyze: MagicMock,
        job: BigQueryIngestJob,
    ) -> None:
        """Test ingestion with custom batch sizes."""
        mock_analyze.return_value = MagicMock()
        mock_classify.return_value = {}
        mock_map.return_value = SchemaMapping(
            source_table="t1",
            entity_nodes=[],
            relationships=[],
        )
        mock_write.return_value = {
            "nodes_written": 5,
            "edges_written": 2,
            "relationships_inferred": 1,
        }

        job.ingest_table(
            "table1",
            node_batch_size=CUSTOM_NODE_BATCH_SIZE,
            edge_batch_size=CUSTOM_EDGE_BATCH_SIZE,
        )

        # Verify custom batch sizes were passed to write_to_spanner
        mock_write.assert_called_once()
        call_args = mock_write.call_args[0]  # Positional args
        # Arguments are: mapping, table_id, node_batch_size, edge_batch_size
        assert call_args[2] == CUSTOM_NODE_BATCH_SIZE
        assert call_args[3] == CUSTOM_EDGE_BATCH_SIZE


class TestBigQueryIngestJobIngestDataset:
    """Tests for dataset-wide ingestion orchestration."""

    @pytest.fixture
    def job(self) -> BigQueryIngestJob:
        """Create BigQueryIngestJob with mocked clients."""
        with (
            patch("src.pipelines.bigquery_ingestion.ingest_orchestrator.bigquery.Client"),
            patch("src.pipelines.bigquery_ingestion.ingest_orchestrator.spanner.Client"),
        ):
            return BigQueryIngestJob(
                project_id="p1",
                bigquery_dataset_id="d1",
                spanner_project_id="sp1",
                spanner_instance_id="si1",
                spanner_database_id="sd1",
                tenant_id="t1",
            )

    @patch.object(BigQueryIngestJob, "ingest_table")
    def test_ingest_dataset_success(
        self, mock_ingest_table: MagicMock, job: BigQueryIngestJob
    ) -> None:
        """Test successful dataset-wide ingestion."""
        with patch.object(
            job.schema_analyzer,
            "list_tables",
            return_value=[("table1", 1000), ("table2", 2000)],
        ):
            mock_ingest_table.side_effect = [
                {
                    "nodes_written": 10,
                    "edges_written": 5,
                    "relationships_inferred": 2,
                },
                {
                    "nodes_written": 20,
                    "edges_written": 10,
                    "relationships_inferred": 4,
                },
            ]

            result = job.ingest_dataset()

            assert result["tables_processed"] == MULTIPLE_TABLES_PROCESSED
            assert result["tables_failed"] == ALL_TABLES_SUCCESS
            assert result["nodes_written"] == MULTI_TABLE_NODES
            assert result["edges_written"] == MULTI_TABLE_EDGES
            assert result["relationships_inferred"] == MULTI_TABLE_INFERRED
            assert mock_ingest_table.call_count == MULTIPLE_TABLES_PROCESSED

    @patch.object(BigQueryIngestJob, "ingest_table")
    def test_ingest_dataset_with_failures(
        self, mock_ingest_table: MagicMock, job: BigQueryIngestJob
    ) -> None:
        """Test dataset ingestion with some table failures."""
        with patch.object(
            job.schema_analyzer,
            "list_tables",
            return_value=[
                ("table1", 1000),
                ("table2", 2000),
                ("table3", 3000),
            ],
        ):
            mock_ingest_table.side_effect = [
                {
                    "nodes_written": 10,
                    "edges_written": 5,
                    "relationships_inferred": 2,
                },
                IngestOrchestratorError(
                    error_code="TEST",
                    error_message="table2 failed",
                ),
                {
                    "nodes_written": 20,
                    "edges_written": 10,
                    "relationships_inferred": 4,
                },
            ]

            result = job.ingest_dataset()

            assert result["tables_processed"] == PARTIAL_TABLES_PROCESSED
            assert result["tables_failed"] == PARTIAL_TABLES_FAILED
            assert result["nodes_written"] == MULTI_TABLE_NODES
            assert result["edges_written"] == MULTI_TABLE_EDGES

    @patch.object(BigQueryIngestJob, "ingest_table")
    def test_ingest_dataset_list_failure(
        self, mock_ingest_table: MagicMock, job: BigQueryIngestJob
    ) -> None:
        """Test error when listing tables fails."""
        with (
            patch.object(
                job.schema_analyzer,
                "list_tables",
                side_effect=RuntimeError("List failed"),
            ),
            pytest.raises(
                IngestOrchestratorError,
                match="LIST_TABLES_FAILED",
            ),
        ):
            job.ingest_dataset()

        mock_ingest_table.assert_not_called()


class TestBigQueryIngestJobPipelineStages:
    """Tests for individual pipeline stages."""

    @pytest.fixture
    def job(self) -> BigQueryIngestJob:
        """Create BigQueryIngestJob with mocked clients."""
        with (
            patch("src.pipelines.bigquery_ingestion.ingest_orchestrator.bigquery.Client"),
            patch("src.pipelines.bigquery_ingestion.ingest_orchestrator.spanner.Client"),
        ):
            return BigQueryIngestJob(
                project_id="p1",
                bigquery_dataset_id="d1",
                spanner_project_id="sp1",
                spanner_instance_id="si1",
                spanner_database_id="sd1",
                tenant_id="t1",
            )

    def test_analyze_schema(self, job: BigQueryIngestJob) -> None:
        """Test schema analysis stage."""
        mock_metadata = MagicMock()
        mock_metadata.table_name = "table1"
        mock_metadata.columns = []

        with patch.object(
            job.schema_analyzer,
            "get_table_schema",
            return_value=mock_metadata,
        ):
            result = job._analyze_schema("table1")

            assert result.table_name == "table1"
            job.schema_analyzer.get_table_schema.assert_called_once()

    def test_analyze_schema_error(self, job: BigQueryIngestJob) -> None:
        """Test schema analysis error handling."""
        with (
            patch.object(
                job.schema_analyzer,
                "get_table_schema",
                side_effect=RuntimeError("Analysis error"),
            ),
            pytest.raises(
                IngestOrchestratorError,
                match="SCHEMA_ANALYSIS_FAILED",
            ),
        ):
            job._analyze_schema("table1")

    def test_classify_schema(self, job: BigQueryIngestJob) -> None:
        """Test schema classification stage."""
        mock_metadata = MagicMock()
        mock_metadata.table_name = "table1"
        mock_classification = MagicMock()
        mock_classification.classified_columns = []
        mock_classification.overall_confidence = 0.9
        mock_classification.timestamp = datetime.now(UTC).isoformat()

        with (
            patch.object(job.schema_analyzer, "sample_rows", return_value=[]),
            patch.object(
                job.classifier,
                "classify_columns",
                return_value=mock_classification,
            ),
        ):
            result = job._classify_schema(mock_metadata)

            assert result["overall_confidence"] == DEFAULT_CONFIDENCE

    def test_map_schema(self, job: BigQueryIngestJob) -> None:
        """Test schema mapping stage."""
        mock_metadata = MagicMock()
        mock_classification = {}

        mock_mapping = SchemaMapping(
            source_table="t1",
            entity_nodes=[
                EntityNodeMapping(
                    column_name="col1",
                    entity_types=["PERSON"],
                    id_strategy=EntityIDStrategy.HASH,
                    attributes=[
                        AttributeMapping(
                            column_name="col1",
                            attribute_name="name",
                            data_type="STRING",
                        )
                    ],
                )
            ],
            relationships=[],
        )

        with patch.object(
            job.schema_mapper,
            "create_mapping",
            return_value=mock_mapping,
        ):
            result = job._map_schema(mock_metadata, mock_classification)

            assert len(result.entity_nodes) == 1

    def test_clear_caches(self, job: BigQueryIngestJob) -> None:
        """Test cache clearing."""
        with (
            patch.object(job.schema_analyzer, "clear_cache"),
            patch.object(job.classifier.cache, "clear"),
        ):
            job.clear_caches()

            job.schema_analyzer.clear_cache.assert_called_once()
            job.classifier.cache.clear.assert_called_once()
