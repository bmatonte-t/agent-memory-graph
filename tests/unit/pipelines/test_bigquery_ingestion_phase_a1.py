"""Unit tests for BigQuery schema analyzer and POLE+O classifier."""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.cloud import bigquery

from src.pipelines.bigquery_ingestion.pole_classifier import (
    ClassificationCache,
    ColumnClassification,
    POLEClassifier,
    TableClassification,
)
from src.pipelines.bigquery_ingestion.schema_analyzer import (
    BigQueryMetadataFetchError,
    BigQuerySchemaAnalyzer,
    ColumnSchema,
    TableMetadata,
)
from src.pipelines.bigquery_ingestion.schema_mapper import (
    EntityIDStrategy,
    SchemaMapper,
)

EXPECTED_TWO_RESULTS = 2
EXPECTED_CUSTOMER_ROW_COUNT = 1000
EXPECTED_CLASSIFIED_COLUMNS = 3
EXPECTED_OVERALL_CONFIDENCE = 0.97
EXPECTED_ENTITY_NODE_COUNT = 4


class TestBigQuerySchemaAnalyzer:
    """Tests for BigQuery schema analyzer."""

    @pytest.fixture
    def mock_bq_client(self) -> MagicMock:
        """Create mock BigQuery client."""
        return MagicMock(spec=bigquery.Client)

    @pytest.fixture
    def analyzer(self, mock_bq_client: MagicMock) -> BigQuerySchemaAnalyzer:
        """Create analyzer with mocked client."""
        return BigQuerySchemaAnalyzer(bq_client=mock_bq_client)

    def test_initialization_default_client(self) -> None:
        """Test initialization with default client."""
        with patch("google.cloud.bigquery.Client"):
            analyzer = BigQuerySchemaAnalyzer()
            assert analyzer.client is not None
            assert analyzer._metadata_cache == {}

    def test_initialization_custom_client(self, mock_bq_client: MagicMock) -> None:
        """Test initialization with custom client."""
        analyzer = BigQuerySchemaAnalyzer(bq_client=mock_bq_client)
        assert analyzer.client == mock_bq_client

    def test_list_tables_success(
        self, analyzer: BigQuerySchemaAnalyzer, mock_bq_client: MagicMock
    ) -> None:
        """Test successful table listing."""
        # Mock dataset and tables
        mock_table_1 = MagicMock()
        mock_table_1.table_id = "customers"
        mock_table_1.reference = "ref1"

        mock_table_2 = MagicMock()
        mock_table_2.table_id = "orders"
        mock_table_2.reference = "ref2"

        # Mock full table data with row counts
        mock_full_1 = MagicMock()
        mock_full_1.num_rows = 1000
        mock_full_2 = MagicMock()
        mock_full_2.num_rows = 5000

        # Mock list_tables return
        mock_bq_client.list_tables.return_value = [
            mock_table_1,
            mock_table_2,
        ]
        mock_bq_client.get_table.side_effect = [mock_full_1, mock_full_2]

        result = analyzer.list_tables("project-1", "dataset-1")

        assert len(result) == EXPECTED_TWO_RESULTS
        assert result[0] == ("customers", EXPECTED_CUSTOMER_ROW_COUNT)
        assert result[1] == ("orders", 5000)

    def test_list_tables_error_handling(
        self, analyzer: BigQuerySchemaAnalyzer, mock_bq_client: MagicMock
    ) -> None:
        """Test error handling in list_tables."""
        mock_bq_client.list_tables.side_effect = Exception("API error")

        with pytest.raises(BigQueryMetadataFetchError) as exc_info:
            analyzer.list_tables("project-1", "dataset-1")

        assert exc_info.value.error_code == "LIST_TABLES_FAILED"
        assert exc_info.value.project_id == "project-1"
        assert exc_info.value.dataset_id == "dataset-1"

    def test_get_table_schema_success(
        self, analyzer: BigQuerySchemaAnalyzer, mock_bq_client: MagicMock
    ) -> None:
        """Test successful schema retrieval."""
        # Mock schema fields
        field_1 = MagicMock()
        field_1.name = "customer_id"
        field_1.field_type = "STRING"
        field_1.mode = "NULLABLE"
        field_1.description = "Customer identifier"

        field_2 = MagicMock()
        field_2.name = "created_at"
        field_2.field_type = "TIMESTAMP"
        field_2.mode = "NULLABLE"
        field_2.description = None

        # Mock full table
        mock_table = MagicMock()
        mock_table.schema = [field_1, field_2]
        mock_table.num_rows = 1000
        mock_table.num_bytes = 1000000
        mock_table.created = None
        mock_table.modified = None

        mock_bq_client.get_table.return_value = mock_table

        metadata = analyzer.get_table_schema("project-1", "dataset-1", "customers")

        assert metadata.table_id == "customers"
        assert metadata.dataset_id == "dataset-1"
        assert len(metadata.columns) == EXPECTED_TWO_RESULTS
        assert metadata.columns[0].name == "customer_id"
        assert metadata.columns[0].field_type == "STRING"
        assert metadata.row_count == EXPECTED_CUSTOMER_ROW_COUNT

    def test_get_table_schema_caching(
        self, analyzer: BigQuerySchemaAnalyzer, mock_bq_client: MagicMock
    ) -> None:
        """Test schema caching."""
        mock_table = MagicMock()
        mock_table.schema = []
        mock_table.num_rows = 100
        mock_table.num_bytes = 10000
        mock_table.created = None
        mock_table.modified = None

        mock_bq_client.get_table.return_value = mock_table

        # First call
        result1 = analyzer.get_table_schema("project-1", "dataset-1", "table-1")
        # Second call (cached)
        result2 = analyzer.get_table_schema("project-1", "dataset-1", "table-1")

        # Verify only one API call
        assert mock_bq_client.get_table.call_count == 1
        assert result1 == result2

    def test_sample_rows_success(
        self, analyzer: BigQuerySchemaAnalyzer, mock_bq_client: MagicMock
    ) -> None:
        """Test row sampling."""
        # Mock query results
        mock_result = [
            {"customer_id": "C001", "name": "Alice"},
            {"customer_id": "C002", "name": "Bob"},
        ]

        mock_job = MagicMock()
        mock_job.result.return_value = [
            MagicMock(items=mock_result[0].items),
            MagicMock(items=mock_result[1].items),
        ]

        mock_bq_client.query.return_value = mock_job

        rows = analyzer.sample_rows("project-1", "dataset-1", "customers", limit=2)

        assert len(rows) == EXPECTED_TWO_RESULTS
        assert rows[0] == {"customer_id": "C001", "name": "Alice"}

    def test_clear_cache(self, analyzer: BigQuerySchemaAnalyzer, mock_bq_client: MagicMock) -> None:
        """Test cache clearing."""
        # Populate cache
        mock_table = MagicMock()
        mock_table.schema = []
        mock_table.num_rows = 100
        mock_table.num_bytes = 10000
        mock_table.created = None
        mock_table.modified = None

        mock_bq_client.get_table.return_value = mock_table
        analyzer.get_table_schema("project-1", "dataset-1", "table-1")

        assert len(analyzer._metadata_cache) == 1

        # Clear cache
        analyzer.clear_cache()
        assert len(analyzer._metadata_cache) == 0


class TestPOLEClassifier:
    """Tests for POLE+O classifier."""

    @pytest.fixture
    def table_metadata(self) -> TableMetadata:
        """Create sample table metadata."""
        return TableMetadata(
            project_id="project-1",
            dataset_id="analytics",
            table_id="customers",
            full_table_id="project-1.analytics.customers",
            columns=[
                ColumnSchema(name="customer_id", field_type="STRING"),
                ColumnSchema(name="first_name", field_type="STRING"),
                ColumnSchema(name="created_at", field_type="TIMESTAMP"),
            ],
            row_count=1000,
        )

    @pytest.fixture
    def sample_rows(self) -> list[dict[str, object]]:
        """Create sample rows."""
        return [
            {"customer_id": "C001", "first_name": "Alice", "created_at": "2026-01-01"},
            {"customer_id": "C002", "first_name": "Bob", "created_at": "2026-01-02"},
        ]

    @pytest.fixture
    def cache(self) -> ClassificationCache:
        """Create classification cache."""
        return ClassificationCache()

    def test_classification_cache_get_miss(self, cache: ClassificationCache) -> None:
        """Test cache miss."""
        result = cache.get("non_existent_key")
        assert result is None

    def test_classification_cache_set_and_get(self, cache: ClassificationCache) -> None:
        """Test cache set and get."""
        classification = TableClassification(
            table_id="test_table",
            dataset_id="test_dataset",
            project_id="test_project",
            classified_columns=[],
            overall_confidence=0.8,
            classification_timestamp="2026-01-01T00:00:00Z",
        )

        cache.set("test_key", classification)
        result = cache.get("test_key")

        assert result == classification

    def test_classification_cache_expiry(self, cache: ClassificationCache) -> None:
        """Test cache expiry."""
        # Create cache with 1-second TTL
        short_cache = ClassificationCache(ttl_hours=1 / 3600)

        classification = TableClassification(
            table_id="test_table",
            dataset_id="test_dataset",
            project_id="test_project",
            classified_columns=[],
            overall_confidence=0.8,
            classification_timestamp="2026-01-01T00:00:00Z",
        )

        short_cache.set("test_key", classification)
        assert short_cache.get("test_key") is not None

        # Wait for expiry
        time.sleep(1.5)
        assert short_cache.get("test_key") is None

    def test_cache_clear(self, cache: ClassificationCache) -> None:
        """Test cache clearing."""
        classification = TableClassification(
            table_id="test_table",
            dataset_id="test_dataset",
            project_id="test_project",
            classified_columns=[],
            overall_confidence=0.8,
            classification_timestamp="2026-01-01T00:00:00Z",
        )

        cache.set("test_key", classification)
        assert len(cache.cache) == 1

        cache.clear()
        assert len(cache.cache) == 0

    @patch("src.pipelines.bigquery_ingestion.pole_classifier.generate_generative_ai_text")
    def test_classify_columns_success(
        self,
        mock_generate_text: MagicMock,
        table_metadata: TableMetadata,
        sample_rows: list[dict[str, object]],
    ) -> None:
        """Test successful column classification."""
        # Mock Gemini response
        gemini_response = {
            "classifications": [
                {
                    "column_name": "customer_id",
                    "entity_types": ["PERSON", "IDENTIFIER"],
                    "confidence_score": 0.95,
                    "rationale": "Unique identifier for customer",
                },
                {
                    "column_name": "first_name",
                    "entity_types": ["PERSON"],
                    "confidence_score": 0.98,
                    "rationale": "Person's first name",
                },
                {
                    "column_name": "created_at",
                    "entity_types": ["EVENT", "TEMPORAL"],
                    "confidence_score": 0.99,
                    "rationale": "Event timestamp",
                },
            ],
            "overall_confidence": 0.97,
        }

        mock_generate_text.return_value = json.dumps(gemini_response)

        classifier = POLEClassifier(project_id="project-1")
        result = classifier.classify_columns(table_metadata, sample_rows)

        assert len(result.classified_columns) == EXPECTED_CLASSIFIED_COLUMNS
        assert result.classified_columns[0].column_name == "customer_id"
        assert set(result.classified_columns[0].entity_types) == {
            "PERSON",
            "IDENTIFIER",
        }
        assert result.overall_confidence == EXPECTED_OVERALL_CONFIDENCE

    @patch("src.pipelines.bigquery_ingestion.pole_classifier.generate_generative_ai_text")
    def test_classify_columns_caching(
        self,
        mock_generate_text: MagicMock,
        table_metadata: TableMetadata,
    ) -> None:
        """Test classification caching."""
        gemini_response: dict[str, Any] = {
            "classifications": [],
            "overall_confidence": 0.8,
        }

        mock_generate_text.return_value = json.dumps(gemini_response)

        cache = ClassificationCache()
        classifier = POLEClassifier(project_id="project-1", cache=cache)

        # First call
        result1 = classifier.classify_columns(table_metadata)
        # Second call (cached)
        result2 = classifier.classify_columns(table_metadata)

        # Should only call Gemini once
        assert mock_generate_text.call_count == 1
        assert result1 == result2


class TestSchemaMapper:
    """Tests for schema mapper."""

    @pytest.fixture
    def table_metadata(self) -> TableMetadata:
        """Create sample table metadata."""
        return TableMetadata(
            project_id="project-1",
            dataset_id="analytics",
            table_id="customers",
            full_table_id="project-1.analytics.customers",
            columns=[
                ColumnSchema(name="customer_id", field_type="STRING"),
                ColumnSchema(name="name", field_type="STRING"),
                ColumnSchema(name="org_id", field_type="STRING"),
                ColumnSchema(name="location", field_type="STRING"),
            ],
        )

    @pytest.fixture
    def classification(self) -> TableClassification:
        """Create sample classification."""
        return TableClassification(
            table_id="customers",
            dataset_id="analytics",
            project_id="project-1",
            classified_columns=[
                ColumnClassification(
                    column_name="customer_id",
                    column_type="STRING",
                    entity_types=["PERSON", "IDENTIFIER"],
                    confidence_score=0.95,
                    rationale="Customer ID",
                ),
                ColumnClassification(
                    column_name="name",
                    column_type="STRING",
                    entity_types=["PERSON"],
                    confidence_score=0.98,
                    rationale="Customer name",
                ),
                ColumnClassification(
                    column_name="org_id",
                    column_type="STRING",
                    entity_types=["ORGANIZATION", "IDENTIFIER"],
                    confidence_score=0.90,
                    rationale="Organization ID",
                ),
                ColumnClassification(
                    column_name="location",
                    column_type="STRING",
                    entity_types=["LOCATION"],
                    confidence_score=0.85,
                    rationale="Location",
                ),
            ],
            overall_confidence=0.92,
            classification_timestamp="2026-01-01T00:00:00Z",
        )

    def test_create_mapping(
        self,
        table_metadata: TableMetadata,
        classification: TableClassification,
    ) -> None:
        """Test schema mapping creation."""
        mapper = SchemaMapper()
        mapping = mapper.create_mapping(table_metadata, classification)

        assert mapping.source_table == "analytics.customers"
        assert len(mapping.entity_nodes) == EXPECTED_ENTITY_NODE_COUNT
        assert mapping.entity_nodes[0].column_name == "customer_id"
        assert mapping.entity_nodes[0].entity_types == ["PERSON", "IDENTIFIER"]

    def test_inferred_relationships(
        self,
        table_metadata: TableMetadata,
        classification: TableClassification,
    ) -> None:
        """Test relationship inference."""
        mapper = SchemaMapper()
        mapping = mapper.create_mapping(table_metadata, classification)

        # Should infer PERSON -> ORGANIZATION relationship
        org_relationships = [r for r in mapping.relationships if r.relation_type == "MEMBER_OF"]
        assert len(org_relationships) > 0

    def test_entity_id_generation_primary_key(
        self, table_metadata: TableMetadata, classification: TableClassification
    ) -> None:
        """Test entity ID generation with primary key strategy."""
        mapper = SchemaMapper()
        mapping = mapper.create_mapping(
            table_metadata, classification, primary_key_column="customer_id"
        )

        # First entity should use primary key strategy
        entity_mapping = mapping.entity_nodes[0]
        assert entity_mapping.id_strategy == EntityIDStrategy.PRIMARY_KEY

        row_data: dict[str, object] = {"customer_id": "C001", "name": "Alice"}
        entity_id = mapper.get_entity_id(mapping, row_data, entity_mapping)

        assert entity_id == "C001"

    def test_entity_id_generation_hash(
        self, table_metadata: TableMetadata, classification: TableClassification
    ) -> None:
        """Test entity ID generation with hash strategy."""
        mapper = SchemaMapper()
        mapping = mapper.create_mapping(table_metadata, classification)

        # Non-primary-key entity should use hash strategy
        entity_mapping = mapping.entity_nodes[1]  # name column
        assert entity_mapping.id_strategy == EntityIDStrategy.HASH

        row_data: dict[str, object] = {"name": "Alice"}
        entity_id = mapper.get_entity_id(mapping, row_data, entity_mapping)

        # Should start with column name
        assert entity_id.startswith("name_")

    def test_clear_mappings(
        self,
        table_metadata: TableMetadata,
        classification: TableClassification,
    ) -> None:
        """Test clearing mappings cache."""
        mapper = SchemaMapper()
        mapper.create_mapping(table_metadata, classification)
        assert len(mapper.mappings) > 0

        mapper.clear_mappings()
        assert len(mapper.mappings) == 0
