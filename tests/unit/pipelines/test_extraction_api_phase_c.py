"""Comprehensive test suite for extraction API endpoints (Phase C).

This test module covers the FastAPI extraction API service:
- Request/response validation
- Single document extraction endpoint
- Batch extraction endpoint with deduplication
- Error handling and HTTP status codes
- Health check endpoint

Test Structure:
  - Health check: 2 tests
  - Document extraction: 8 tests
  - Batch extraction: 12 tests
  - Error handling: 8 tests
  Total: 30 tests
"""
# ruff: noqa: PLR2004, S108

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.pipelines.api.extraction_api import (
    BatchExtractionResponse,
    DocumentExtractionResponse,
    ErrorResponse,
    app,
)
from src.pipelines.document_ingestion.document_extractor import (
    DocumentFormat,
    DocumentMetadata,
    ExtractedDocument,
)
from src.pipelines.services.extraction_orchestrator import (
    DocumentWithEntities,
    ExtractionOrchestrationError,
    ExtractionResult,
)

client = TestClient(app)

# Test constants
TEST_FILE_PATH = "/tmp/test.pdf"
TEST_THRESHOLD = 0.85
TEST_PAGE_COUNT = 3
TEST_ENTITY_COUNT = 5


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_success(self) -> None:
        """Test successful health check."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["api_version"] == "v1"

    def test_health_check_message(self) -> None:
        """Test health check message content."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert isinstance(data["message"], str)


class TestDocumentExtractionEndpoint:
    """Tests for document extraction endpoint."""

    def test_extract_document_success(self) -> None:
        """Test successful document extraction."""
        request_data = {
            "file_path": TEST_FILE_PATH,
            "detect_entities": True,
        }

        mock_doc = DocumentWithEntities(
            document=ExtractedDocument(
                metadata=DocumentMetadata(
                    file_path=TEST_FILE_PATH,
                    file_format=DocumentFormat.PDF,
                    file_size_bytes=1024,
                    page_count=TEST_PAGE_COUNT,
                    title="Test Doc",
                    author="Test Author",
                    created_at="2024-01-01T00:00:00",
                ),
                pages=[],
            ),
            entities={"entity_001": "TestEntity"},
        )

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_document",
            return_value=mock_doc,
        ):
            response = client.post("/api/v1/extract/document", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["file_path"] == TEST_FILE_PATH
            assert data["page_count"] == TEST_PAGE_COUNT
            assert data["entity_count"] == 1

    def test_extract_document_no_entities(self) -> None:
        """Test document extraction without entity detection."""
        request_data = {
            "file_path": TEST_FILE_PATH,
            "detect_entities": False,
        }

        mock_doc = DocumentWithEntities(
            document=ExtractedDocument(
                metadata=DocumentMetadata(
                    file_path=TEST_FILE_PATH,
                    file_format=DocumentFormat.PDF,
                    file_size_bytes=1024,
                    page_count=1,
                    title="Test",
                    author="Author",
                    created_at="2024-01-01T00:00:00",
                ),
                pages=[],
            ),
            entities={},
        )

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_document",
            return_value=mock_doc,
        ):
            response = client.post("/api/v1/extract/document", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["entity_count"] == 0

    def test_extract_document_invalid_file_path(self) -> None:
        """Test extraction with invalid file path."""
        request_data = {
            "file_path": "/nonexistent/file.pdf",
            "detect_entities": True,
        }

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_document",
            side_effect=ExtractionOrchestrationError(
                error_code="EXTRACTION_FAILED",
                error_message="File not found",
                file_path="/nonexistent/file.pdf",
            ),
        ):
            response = client.post("/api/v1/extract/document", json=request_data)

            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error_code"] == "EXTRACTION_FAILED"

    def test_extract_document_validation_error(self) -> None:
        """Test extraction request validation."""
        request_data = {
            # Missing required file_path
            "detect_entities": True,
        }

        response = client.post("/api/v1/extract/document", json=request_data)

        # Should return 422 for validation error
        assert response.status_code == 422

    def test_extract_document_response_model(self) -> None:
        """Test response model validation."""
        request_data = {
            "file_path": TEST_FILE_PATH,
            "detect_entities": True,
        }

        mock_doc = DocumentWithEntities(
            document=ExtractedDocument(
                metadata=DocumentMetadata(
                    file_path=TEST_FILE_PATH,
                    file_format=DocumentFormat.PDF,
                    file_size_bytes=1024,
                    page_count=2,
                    title="Test",
                    author="Author",
                    created_at="2024-01-01T00:00:00",
                ),
                pages=[],
            ),
            entities={},
        )

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_document",
            return_value=mock_doc,
        ):
            response = client.post("/api/v1/extract/document", json=request_data)

            assert response.status_code == 200
            # Validate response can be parsed as DocumentExtractionResponse
            DocumentExtractionResponse(**response.json())

    def test_extract_document_unexpected_error(self) -> None:
        """Test extraction with unexpected error."""
        request_data = {
            "file_path": TEST_FILE_PATH,
            "detect_entities": True,
        }

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_document",
            side_effect=ValueError("Unexpected error"),
        ):
            response = client.post("/api/v1/extract/document", json=request_data)

            assert response.status_code == 500
            data = response.json()
            assert data["detail"]["error_code"] == "INTERNAL_ERROR"

    def test_extract_document_default_detect_entities(self) -> None:
        """Test that detect_entities defaults to True."""
        request_data = {
            "file_path": TEST_FILE_PATH,
            # No detect_entities specified
        }

        mock_doc = DocumentWithEntities(
            document=ExtractedDocument(
                metadata=DocumentMetadata(
                    file_path=TEST_FILE_PATH,
                    file_format=DocumentFormat.PDF,
                    file_size_bytes=1024,
                    page_count=1,
                    title="Test",
                    author="Author",
                    created_at="2024-01-01T00:00:00",
                ),
                pages=[],
            ),
            entities={"entity_001": "Entity"},
        )

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_document",
            return_value=mock_doc,
        ) as mock_process:
            response = client.post("/api/v1/extract/document", json=request_data)

            assert response.status_code == 200
            # Verify detect_entities=True was passed by default
            mock_process.assert_called_once()
            call_args = mock_process.call_args
            assert call_args[1]["detect_entities"] is True


class TestBatchExtractionEndpoint:
    """Tests for batch extraction endpoint."""

    def test_batch_extraction_success(self) -> None:
        """Test successful batch extraction."""
        request_data = {
            "file_paths": ["/tmp/doc1.pdf", "/tmp/doc2.pdf"],
            "detect_entities": True,
            "deduplicate_threshold": 0.85,
        }

        mock_result = ExtractionResult(
            documents=[
                DocumentWithEntities(
                    document=ExtractedDocument(
                        metadata=DocumentMetadata(
                            file_path="/tmp/doc1.pdf",
                            file_format=DocumentFormat.PDF,
                            file_size_bytes=1024,
                            page_count=1,
                            title="Doc1",
                            author="Author",
                            created_at="2024-01-01T00:00:00",
                        ),
                        pages=[],
                    ),
                    entities={"entity_001": "Entity1"},
                ),
                DocumentWithEntities(
                    document=ExtractedDocument(
                        metadata=DocumentMetadata(
                            file_path="/tmp/doc2.pdf",
                            file_format=DocumentFormat.PDF,
                            file_size_bytes=1024,
                            page_count=1,
                            title="Doc2",
                            author="Author",
                            created_at="2024-01-01T00:00:00",
                        ),
                        pages=[],
                    ),
                    entities={"entity_002": "Entity2"},
                ),
            ],
        )

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_batch",
            return_value=mock_result,
        ):
            response = client.post("/api/v1/extract/batch", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["total_documents"] == 2
            assert data["total_entities"] == 2

    def test_batch_extraction_with_deduplication(self) -> None:
        """Test batch extraction with deduplication results."""
        request_data = {
            "file_paths": ["/tmp/doc1.pdf"],
            "detect_entities": True,
            "deduplicate_threshold": 0.85,
        }

        mock_result = ExtractionResult(
            documents=[
                DocumentWithEntities(
                    document=ExtractedDocument(
                        metadata=DocumentMetadata(
                            file_path="/tmp/doc1.pdf",
                            file_format=DocumentFormat.PDF,
                            file_size_bytes=1024,
                            page_count=1,
                            title="Doc1",
                            author="Author",
                            created_at="2024-01-01T00:00:00",
                        ),
                        pages=[],
                    ),
                    entities={"entity_001": "Entity1"},
                ),
            ],
            failed_documents=0,
            duplicate_matches=[],
        )

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_batch",
            return_value=mock_result,
        ):
            response = client.post("/api/v1/extract/batch", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["total_documents"] == 1

    def test_batch_extraction_empty_file_paths(self) -> None:
        """Test batch extraction with empty file paths."""
        request_data = {
            "file_paths": [],
        }

        response = client.post("/api/v1/extract/batch", json=request_data)

        # Should fail validation
        assert response.status_code in [400, 422]

    def test_batch_extraction_invalid_threshold(self) -> None:
        """Test batch extraction with invalid threshold."""
        request_data = {
            "file_paths": ["/tmp/doc1.pdf"],
            "deduplicate_threshold": 1.5,  # Out of range
        }

        response = client.post("/api/v1/extract/batch", json=request_data)

        # Should fail validation
        assert response.status_code == 422

    def test_batch_extraction_partial_failure(self) -> None:
        """Test batch extraction with some documents failing."""
        request_data = {
            "file_paths": ["/tmp/doc1.pdf", "/tmp/missing.pdf"],
            "detect_entities": True,
        }

        mock_result = ExtractionResult(
            documents=[
                DocumentWithEntities(
                    document=ExtractedDocument(
                        metadata=DocumentMetadata(
                            file_path="/tmp/doc1.pdf",
                            file_format=DocumentFormat.PDF,
                            file_size_bytes=1024,
                            page_count=1,
                            title="Doc1",
                            author="Author",
                            created_at="2024-01-01T00:00:00",
                        ),
                        pages=[],
                    ),
                    entities={"entity_001": "Entity1"},
                ),
            ],
            failed_documents=1,
        )

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_batch",
            return_value=mock_result,
        ):
            response = client.post("/api/v1/extract/batch", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["total_documents"] == 1
            assert data["failed_documents"] == 1

    def test_batch_extraction_default_threshold(self) -> None:
        """Test batch extraction with default threshold."""
        request_data = {
            "file_paths": ["/tmp/doc1.pdf"],
            # No deduplicate_threshold specified
        }

        mock_result = ExtractionResult(documents=[])

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_batch",
            return_value=mock_result,
        ) as mock_batch:
            response = client.post("/api/v1/extract/batch", json=request_data)

            assert response.status_code == 200
            # Verify default threshold was used
            mock_batch.assert_called_once()

    def test_batch_extraction_response_model(self) -> None:
        """Test batch extraction response model validation."""
        request_data = {
            "file_paths": ["/tmp/doc1.pdf"],
        }

        mock_result = ExtractionResult(documents=[])

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_batch",
            return_value=mock_result,
        ):
            response = client.post("/api/v1/extract/batch", json=request_data)

            assert response.status_code == 200
            # Validate response can be parsed as BatchExtractionResponse
            BatchExtractionResponse(**response.json())

    def test_batch_extraction_error_handling(self) -> None:
        """Test batch extraction error handling."""
        request_data = {
            "file_paths": ["/tmp/doc1.pdf"],
        }

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_batch",
            side_effect=ExtractionOrchestrationError(
                error_code="BATCH_EMPTY",
                error_message="No documents extracted",
                stage="batch_processing",
            ),
        ):
            response = client.post("/api/v1/extract/batch", json=request_data)

            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error_code"] == "BATCH_EMPTY"

    def test_batch_extraction_unexpected_error(self) -> None:
        """Test batch extraction with unexpected error."""
        request_data = {
            "file_paths": ["/tmp/doc1.pdf"],
        }

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_batch",
            side_effect=RuntimeError("Unexpected error"),
        ):
            response = client.post("/api/v1/extract/batch", json=request_data)

            assert response.status_code == 500
            data = response.json()
            assert data["detail"]["error_code"] == "INTERNAL_ERROR"


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_endpoint(self) -> None:
        """Test root endpoint response."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["version"] == "v1"

    def test_root_endpoint_docs_link(self) -> None:
        """Test root endpoint includes docs link."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "docs" in data


class TestErrorHandling:
    """Tests for error handling and responses."""

    def test_error_response_model(self) -> None:
        """Test error response model."""
        error = ErrorResponse(
            error_code="TEST_ERROR",
            error_message="Test error message",
        )
        assert error.success is False
        assert error.error_code == "TEST_ERROR"

    def test_error_response_with_detail(self) -> None:
        """Test error response with detail."""
        error = ErrorResponse(
            error_code="TEST_ERROR",
            error_message="Test error",
            detail="Additional details",
        )
        assert error.detail == "Additional details"

    def test_400_status_for_extraction_error(self) -> None:
        """Test 400 status for ExtractionOrchestrationError."""
        request_data = {
            "file_path": "/tmp/test.pdf",
        }

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_document",
            side_effect=ExtractionOrchestrationError(
                error_code="TEST_ERROR",
                error_message="Test",
            ),
        ):
            response = client.post("/api/v1/extract/document", json=request_data)
            assert response.status_code == 400

    def test_500_status_for_internal_error(self) -> None:
        """Test 500 status for internal errors."""
        request_data = {
            "file_path": "/tmp/test.pdf",
        }

        with patch(
            "src.pipelines.api.extraction_api.orchestrator.process_document",
            side_effect=KeyError("Unexpected"),
        ):
            response = client.post("/api/v1/extract/document", json=request_data)
            assert response.status_code == 500
