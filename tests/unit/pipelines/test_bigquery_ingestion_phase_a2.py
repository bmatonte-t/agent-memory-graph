"""Unit tests for Phase A2: Spanner writer and BigQuery graph mapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from google.cloud import bigquery, spanner

from src.pipelines.bigquery_ingestion.bigquery_graph_mapper import (
    BigQueryGraphMapper,
    BigQueryGraphMapperError,
)
from src.pipelines.bigquery_ingestion.spanner_writer import (
    MemoryEdgeBatch,
    MemoryNodeBatch,
    SpannerIngestWriter,
    SpannerWriteError,
)

# Test constants
SINGLE_NODE_WRITTEN = 1
MULTIPLE_NODES_WRITTEN = 2
SINGLE_EDGE_WRITTEN = 1
MULTIPLE_EDGES_WRITTEN = 2
UPDATE_CALL_COUNT = 1
MULTIPLE_UPDATE_CALLS = 2
DEFAULT_CONFIDENCE = 0.9
WEIGHT_MEDIUM = 0.5
WEIGHT_HIGH = 0.8
WEIGHT_ZERO = 0.0
CONFIDENCE_THRESHOLD = 0.7


class TestMemoryNodeBatch:
    """Tests for MemoryNodeBatch."""

    def test_initialization_basic(self) -> None:
        """Test basic MemoryNodeBatch initialization."""
        node = MemoryNodeBatch(
            tenant_id="tenant-1",
            node_id="node-abc",
            entity_label="PERSON",
            entity_value="John Doe",
        )

        assert node.tenant_id == "tenant-1"
        assert node.node_id == "node-abc"
        assert node.entity_label == "PERSON"
        assert node.entity_value == "John Doe"
        assert node.cognitive_weight == WEIGHT_MEDIUM

    def test_cognitive_weight_bounds(self) -> None:
        """Test cognitive weight is clamped to [0.0, 1.0]."""
        node_below = MemoryNodeBatch(
            tenant_id="t1",
            node_id="n1",
            entity_label="OBJECT",
            entity_value="obj",
            cognitive_weight=-0.5,
        )
        assert node_below.cognitive_weight == WEIGHT_ZERO

        node_above = MemoryNodeBatch(
            tenant_id="t1",
            node_id="n1",
            entity_label="OBJECT",
            entity_value="obj",
            cognitive_weight=1.5,
        )
        assert node_above.cognitive_weight == 1.0

    def test_to_dict(self) -> None:
        """Test conversion to Spanner dict."""
        attrs = {"column_name": "customer_name", "data_type": "STRING"}
        node = MemoryNodeBatch(
            tenant_id="t1",
            node_id="n1",
            entity_label="PERSON",
            entity_value="Alice",
            cognitive_weight=0.8,
            attributes=attrs,
        )

        result = node.to_dict()
        assert result["tenant_id"] == "t1"
        assert result["node_id"] == "n1"
        assert result["entity_label"] == "PERSON"
        assert result["entity_value"] == "Alice"
        assert result["cognitive_weight"] == WEIGHT_HIGH
        assert result["attributes"] == attrs


class TestMemoryEdgeBatch:
    """Tests for MemoryEdgeBatch."""

    def test_initialization_basic(self) -> None:
        """Test basic MemoryEdgeBatch initialization."""
        edge = MemoryEdgeBatch(
            tenant_id="tenant-1",
            source_node_id="person-1",
            target_node_id="org-1",
            relation_type="MEMBER_OF",
        )

        assert edge.tenant_id == "tenant-1"
        assert edge.source_node_id == "person-1"
        assert edge.target_node_id == "org-1"
        assert edge.relation_type == "MEMBER_OF"
        assert edge.confidence == WEIGHT_HIGH
        assert edge.inferred is False

    def test_confidence_bounds(self) -> None:
        """Test confidence is clamped to [0.0, 1.0]."""
        edge_low = MemoryEdgeBatch(
            tenant_id="t1",
            source_node_id="s1",
            target_node_id="t1",
            relation_type="REL",
            confidence=-0.2,
        )
        assert edge_low.confidence == WEIGHT_ZERO

        edge_high = MemoryEdgeBatch(
            tenant_id="t1",
            source_node_id="s1",
            target_node_id="t1",
            relation_type="REL",
            confidence=2.0,
        )
        assert edge_high.confidence == 1.0

    def test_to_dict(self) -> None:
        """Test conversion to Spanner dict."""
        edge = MemoryEdgeBatch(
            tenant_id="t1",
            source_node_id="p1",
            target_node_id="o1",
            relation_type="LOCATED_AT",
            confidence=0.9,
            inferred=True,
        )

        result = edge.to_dict()
        assert result["tenant_id"] == "t1"
        assert result["source_node_id"] == "p1"
        assert result["target_node_id"] == "o1"
        assert result["relation_type"] == "LOCATED_AT"
        assert result["confidence"] == DEFAULT_CONFIDENCE
        assert result["inferred"] is True


class TestSpannerIngestWriter:
    """Tests for SpannerIngestWriter."""

    @pytest.fixture
    def mock_spanner_client(self) -> MagicMock:
        """Mock Spanner client."""
        return MagicMock(spec=spanner.Client)

    @pytest.fixture
    def writer(self, mock_spanner_client: MagicMock) -> SpannerIngestWriter:
        """Create SpannerIngestWriter with mocked client."""
        return SpannerIngestWriter(
            project_id="project-1",
            instance_id="instance-1",
            database_id="db-1",
            client=mock_spanner_client,
        )

    def test_initialization_valid(self) -> None:
        """Test valid initialization."""
        with patch.object(spanner, "Client"):
            writer = SpannerIngestWriter(project_id="p1", instance_id="i1", database_id="d1")
            assert writer.project_id == "p1"
            assert writer.instance_id == "i1"
            assert writer.database_id == "d1"

    def test_initialization_missing_params(self) -> None:
        """Test initialization fails with missing parameters."""
        with pytest.raises(ValueError, match="required"):
            SpannerIngestWriter(project_id="", instance_id="i1", database_id="d1")

    def test_write_nodes_empty(self, writer: SpannerIngestWriter) -> None:
        """Test write_nodes with empty list."""
        result = writer.write_nodes("tenant-1", [])
        assert result == 0

    def test_write_nodes_success(
        self, writer: SpannerIngestWriter, mock_spanner_client: MagicMock
    ) -> None:
        """Test successful node write."""
        mock_batch = MagicMock()
        mock_batch_ref = mock_spanner_client.instance.return_value.database.return_value.batch
        mock_batch_ref.return_value.__enter__.return_value = mock_batch

        nodes = [
            MemoryNodeBatch(
                tenant_id="t1",
                node_id="n1",
                entity_label="PERSON",
                entity_value="Alice",
            ),
            MemoryNodeBatch(
                tenant_id="t1",
                node_id="n2",
                entity_label="OBJECT",
                entity_value="Device",
            ),
        ]

        result = writer.write_nodes("t1", nodes)
        assert result == MULTIPLE_NODES_WRITTEN
        assert mock_batch.execute_update.call_count == MULTIPLE_NODES_WRITTEN

    def test_write_nodes_failure(
        self, writer: SpannerIngestWriter, mock_spanner_client: MagicMock
    ) -> None:
        """Test write_nodes error handling."""
        mock_batch = mock_spanner_client.instance.return_value.database.return_value.batch
        mock_batch.return_value.__enter__.side_effect = Exception("Connection error")

        nodes = [MemoryNodeBatch(tenant_id="t1", node_id="n1", entity_label="P", entity_value="x")]

        with pytest.raises(SpannerWriteError) as exc_info:
            writer.write_nodes("t1", nodes)

        assert exc_info.value.error_code == "WRITE_NODES_FAILED"
        assert exc_info.value.table_name == "MemoryNode"

    def test_write_edges_empty(self, writer: SpannerIngestWriter) -> None:
        """Test write_edges with empty list."""
        result = writer.write_edges("tenant-1", [])
        assert result == 0

    def test_write_edges_success(
        self, writer: SpannerIngestWriter, mock_spanner_client: MagicMock
    ) -> None:
        """Test successful edge write."""
        mock_batch = MagicMock()
        mock_batch_ref = mock_spanner_client.instance.return_value.database.return_value.batch
        mock_batch_ref.return_value.__enter__.return_value = mock_batch

        edges = [
            MemoryEdgeBatch(
                tenant_id="t1",
                source_node_id="n1",
                target_node_id="n2",
                relation_type="MEMBER_OF",
            ),
        ]

        result = writer.write_edges("t1", edges)
        assert result == 1
        assert mock_batch.execute_update.call_count == 1

    def test_write_edges_failure(
        self, writer: SpannerIngestWriter, mock_spanner_client: MagicMock
    ) -> None:
        """Test write_edges error handling."""
        mock_batch_ref = mock_spanner_client.instance.return_value.database.return_value.batch
        mock_batch_ref.return_value.__enter__.side_effect = Exception("Quota exceeded")

        edges = [
            MemoryEdgeBatch(
                tenant_id="t1",
                source_node_id="n1",
                target_node_id="n2",
                relation_type="REL",
            )
        ]

        with pytest.raises(SpannerWriteError) as exc_info:
            writer.write_edges("t1", edges)

        assert exc_info.value.error_code == "WRITE_EDGES_FAILED"
        assert exc_info.value.table_name == "MemoryEdge"

    def test_record_engram_evidence_success(
        self, writer: SpannerIngestWriter, mock_spanner_client: MagicMock
    ) -> None:
        """Test successful ENGRAM_EVIDENCE recording."""
        mock_batch = MagicMock()
        mock_batch_ref = mock_spanner_client.instance.return_value.database.return_value.batch
        mock_batch_ref.return_value.__enter__.return_value = mock_batch

        provenance = {
            "project_id": "p1",
            "dataset_id": "d1",
            "table_id": "t1",
        }
        writer.record_engram_evidence("t1", "n1", "bigquery_table", provenance)

        mock_batch.execute_update.assert_called_once()

    def test_record_engram_evidence_failure(
        self, writer: SpannerIngestWriter, mock_spanner_client: MagicMock
    ) -> None:
        """Test ENGRAM_EVIDENCE recording error."""
        mock_batch_ref = mock_spanner_client.instance.return_value.database.return_value.batch
        mock_batch_ref.return_value.__enter__.side_effect = Exception("Write error")

        with pytest.raises(SpannerWriteError) as exc_info:
            writer.record_engram_evidence("t1", "n1", "bigquery_table", {"x": "y"})

        assert exc_info.value.error_code == "RECORD_EVIDENCE_FAILED"
        assert exc_info.value.table_name == "ENGRAM_EVIDENCE"


class TestBigQueryGraphMapper:
    """Tests for BigQueryGraphMapper."""

    @pytest.fixture
    def mock_bq_client(self) -> MagicMock:
        """Mock BigQuery client."""
        return MagicMock(spec=bigquery.Client)

    @pytest.fixture
    def mapper(self, mock_bq_client: MagicMock) -> BigQueryGraphMapper:
        """Create BigQueryGraphMapper with mocked client."""
        return BigQueryGraphMapper(
            project_id="project-1",
            dataset_id="dataset-1",
            client=mock_bq_client,
        )

    def test_initialization_valid(self) -> None:
        """Test valid initialization."""
        with patch.object(bigquery, "Client"):
            mapper = BigQueryGraphMapper(project_id="p1", dataset_id="d1")
            assert mapper.project_id == "p1"
            assert mapper.dataset_id == "d1"

    def test_initialization_missing_params(self) -> None:
        """Test initialization fails with missing parameters."""
        with pytest.raises(ValueError, match="required"):
            BigQueryGraphMapper(project_id="", dataset_id="d1")

    def test_create_entity_view_basic(
        self, mapper: BigQueryGraphMapper, mock_bq_client: MagicMock
    ) -> None:
        """Test basic entity view creation."""
        mock_job = MagicMock()
        mock_bq_client.query.return_value = mock_job

        view_name = mapper.create_entity_view(
            source_table="project-1.dataset-1.MemoryNode",
            tenant_id="tenant-1",
        )

        assert view_name == "vw_entities_tenant-1"
        mock_bq_client.query.assert_called_once()
        mock_job.result.assert_called_once()

    def test_create_entity_view_with_filters(
        self, mapper: BigQueryGraphMapper, mock_bq_client: MagicMock
    ) -> None:
        """Test entity view creation with entity type filters."""
        mock_job = MagicMock()
        mock_bq_client.query.return_value = mock_job

        view_name = mapper.create_entity_view(
            source_table="p.d.MemoryNode",
            tenant_id="t1",
            entity_types=["PERSON", "ORGANIZATION", "INVALID_TYPE"],
            min_cognitive_weight=0.6,
        )

        assert view_name == "vw_entities_t1"
        mock_job.result.assert_called_once()

    def test_create_entity_view_failure(
        self, mapper: BigQueryGraphMapper, mock_bq_client: MagicMock
    ) -> None:
        """Test entity view creation error handling."""
        mock_bq_client.query.side_effect = Exception("Query error")

        with pytest.raises(BigQueryGraphMapperError) as exc_info:
            mapper.create_entity_view("p.d.Node", "t1")

        assert exc_info.value.error_code == "CREATE_ENTITY_VIEW_FAILED"
        assert exc_info.value.dataset_id == "dataset-1"

    def test_create_relationship_view_basic(
        self, mapper: BigQueryGraphMapper, mock_bq_client: MagicMock
    ) -> None:
        """Test basic relationship view creation."""
        mock_job = MagicMock()
        mock_bq_client.query.return_value = mock_job

        view_name = mapper.create_relationship_view(
            source_edge_table="p.d.MemoryEdge",
            source_node_table="p.d.MemoryNode",
            tenant_id="t1",
        )

        assert view_name == "vw_relationships_t1"
        mock_bq_client.query.assert_called_once()

    def test_create_relationship_view_with_filters(
        self, mapper: BigQueryGraphMapper, mock_bq_client: MagicMock
    ) -> None:
        """Test relationship view creation with type filters."""
        mock_job = MagicMock()
        mock_bq_client.query.return_value = mock_job

        view_name = mapper.create_relationship_view(
            source_edge_table="p.d.MemoryEdge",
            source_node_table="p.d.MemoryNode",
            tenant_id="t1",
            relation_types=["MEMBER_OF", "INVALID_REL"],
            min_confidence=0.8,
        )

        assert view_name == "vw_relationships_t1"
        mock_bq_client.query.assert_called_once()

    def test_create_relationship_view_failure(
        self, mapper: BigQueryGraphMapper, mock_bq_client: MagicMock
    ) -> None:
        """Test relationship view creation error."""
        mock_bq_client.query.side_effect = Exception("SQL error")

        with pytest.raises(BigQueryGraphMapperError) as exc_info:
            mapper.create_relationship_view("p.d.Edge", "p.d.Node", "t1")

        assert exc_info.value.error_code == "CREATE_RELATIONSHIP_VIEW_FAILED"

    def test_create_paths_view_basic(
        self, mapper: BigQueryGraphMapper, mock_bq_client: MagicMock
    ) -> None:
        """Test basic paths view creation."""
        mock_job = MagicMock()
        mock_bq_client.query.return_value = mock_job

        view_name = mapper.create_paths_view(
            source_edge_table="p.d.MemoryEdge",
            source_node_table="p.d.MemoryNode",
            tenant_id="t1",
            max_depth=2,
        )

        assert view_name == "vw_paths_t1"
        mock_bq_client.query.assert_called_once()

    def test_create_paths_view_failure(
        self, mapper: BigQueryGraphMapper, mock_bq_client: MagicMock
    ) -> None:
        """Test paths view creation error."""
        mock_bq_client.query.side_effect = Exception("Recursive query error")

        with pytest.raises(BigQueryGraphMapperError) as exc_info:
            mapper.create_paths_view("p.d.Edge", "p.d.Node", "t1")

        assert exc_info.value.error_code == "CREATE_PATHS_VIEW_FAILED"

    def test_drop_view_success(
        self, mapper: BigQueryGraphMapper, mock_bq_client: MagicMock
    ) -> None:
        """Test successful view drop."""
        mapper.drop_view("vw_test")
        mock_bq_client.delete_table.assert_called_once()

    def test_drop_view_not_found(
        self, mapper: BigQueryGraphMapper, mock_bq_client: MagicMock
    ) -> None:
        """Test drop view with not-found (graceful)."""
        mock_bq_client.delete_table.return_value = None
        mapper.drop_view("nonexistent")
        mock_bq_client.delete_table.assert_called_once()

    def test_drop_view_failure(
        self, mapper: BigQueryGraphMapper, mock_bq_client: MagicMock
    ) -> None:
        """Test drop view error handling."""
        mock_bq_client.delete_table.side_effect = Exception("Delete error")

        with pytest.raises(BigQueryGraphMapperError) as exc_info:
            mapper.drop_view("vw_test")

        assert exc_info.value.error_code == "DROP_VIEW_FAILED"
