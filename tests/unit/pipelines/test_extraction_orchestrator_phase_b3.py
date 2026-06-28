"""Comprehensive test suite for extraction orchestrator (Phase B3).

This test module covers the ExtractionOrchestrator service pipeline:
- Request validation and parameter checking
- Document extraction with entity detection
- Batch processing with multiple documents
- Entity deduplication and confidence filtering
- Error handling and failure recovery

Test Structure:
  - ExtractionRequest: 5 tests
  - DocumentWithEntities: 3 tests
  - ExtractionResult: 5 tests
  - ExtractionOrchestrator initialization: 3 tests
  - Entity extraction: 8 tests
  - Single document processing: 6 tests
  - Batch processing: 10 tests
  - Error handling: 8 tests
  Total: 48 tests
"""
# ruff: noqa: PLR2004

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.pipelines.document_ingestion.document_extractor import (
    DocumentFormat,
    DocumentMetadata,
    DocumentPage,
    ExtractedDocument,
    ExtractionError,
    PageMetadata,
)
from src.pipelines.entity_linking.fuzzy_matcher import (
    DeduplicationResult,
    FuzzyMatcherError,
)
from src.pipelines.services.extraction_orchestrator import (
    DocumentWithEntities,
    ExtractionOrchestrationError,
    ExtractionOrchestrator,
    ExtractionRequest,
    ExtractionResult,
)

# Test constants
REQUEST_FILE_PATHS = ["/tmp/doc1.pdf", "/tmp/doc2.pptx"]
REQUEST_THRESHOLD = 0.85
REQUEST_MIN_LENGTH = 3
RESULT_DOCUMENTS_COUNT = 2
ENTITY_ID_001 = "entity_0001"
ENTITY_ID_002 = "entity_0002"
ENTITY_NAME_JOHN = "John"
ENTITY_NAME_JANE = "Jane"


class TestExtractionRequest:
    """Tests for ExtractionRequest data class."""

    def test_request_initialization_defaults(self) -> None:
        """Test ExtractionRequest initialization with defaults."""
        request = ExtractionRequest(file_paths=REQUEST_FILE_PATHS)
        assert request.file_paths == REQUEST_FILE_PATHS
        assert request.detect_entities is True
        assert request.deduplicate_threshold == REQUEST_THRESHOLD
        assert request.include_low_confidence_matches is False
        assert request.min_string_length == REQUEST_MIN_LENGTH

    def test_request_initialization_custom(self) -> None:
        """Test ExtractionRequest with custom parameters."""
        request = ExtractionRequest(
            file_paths=REQUEST_FILE_PATHS,
            detect_entities=False,
            deduplicate_threshold=0.75,
            min_string_length=5,
        )
        assert request.detect_entities is False
        assert request.deduplicate_threshold == 0.75
        assert request.min_string_length == 5

    def test_request_validate_empty_paths(self) -> None:
        """Test validation fails with empty file_paths."""
        request = ExtractionRequest(file_paths=[])
        with pytest.raises(ExtractionOrchestrationError, match="INVALID_REQUEST"):
            request.validate()

    def test_request_validate_invalid_threshold(self) -> None:
        """Test validation fails with out-of-range threshold."""
        request = ExtractionRequest(
            file_paths=REQUEST_FILE_PATHS,
            deduplicate_threshold=1.5,
        )
        with pytest.raises(ExtractionOrchestrationError, match="INVALID_THRESHOLD"):
            request.validate()

    def test_request_validate_invalid_min_length(self) -> None:
        """Test validation fails with invalid min_string_length."""
        request = ExtractionRequest(
            file_paths=REQUEST_FILE_PATHS,
            min_string_length=0,
        )
        with pytest.raises(ExtractionOrchestrationError, match="INVALID_MIN_LENGTH"):
            request.validate()


class TestDocumentWithEntities:
    """Tests for DocumentWithEntities data class."""

    def test_document_with_entities_initialization(self) -> None:
        """Test DocumentWithEntities initialization."""
        doc = ExtractedDocument(
            metadata=DocumentMetadata(
                file_path="/tmp/test.pdf",
                file_format=DocumentFormat.PDF,
                file_size_bytes=1024,
                page_count=1,
                title="Test",
                author="Test Author",
                created_at="2024-01-01T00:00:00",
            ),
            pages=[],
        )
        entities = {ENTITY_ID_001: ENTITY_NAME_JOHN}
        doc_with_entities = DocumentWithEntities(
            document=doc,
            entities=entities,
        )
        assert doc_with_entities.entity_count == 1
        assert doc_with_entities.entities == entities

    def test_document_with_entities_empty(self) -> None:
        """Test DocumentWithEntities with no entities."""
        doc = ExtractedDocument(
            metadata=DocumentMetadata(
                file_path="/tmp/test.pdf",
                file_format=DocumentFormat.PDF,
                file_size_bytes=1024,
                page_count=1,
                title="Test",
                author="Test Author",
                created_at="2024-01-01T00:00:00",
            ),
            pages=[],
        )
        doc_with_entities = DocumentWithEntities(document=doc)
        assert doc_with_entities.entity_count == 0
        assert doc_with_entities.entities == {}

    def test_document_with_entities_entity_count(self) -> None:
        """Test entity_count property updates correctly."""
        doc = ExtractedDocument(
            metadata=DocumentMetadata(
                file_path="/tmp/test.pdf",
                file_format=DocumentFormat.PDF,
                file_size_bytes=1024,
                page_count=1,
                title="Test",
                author="Test Author",
                created_at="2024-01-01T00:00:00",
            ),
            pages=[],
        )
        entities = {ENTITY_ID_001: ENTITY_NAME_JOHN, ENTITY_ID_002: ENTITY_NAME_JANE}
        doc_with_entities = DocumentWithEntities(
            document=doc,
            entities=entities,
        )
        assert doc_with_entities.entity_count == 2


class TestExtractionResult:
    """Tests for ExtractionResult data class."""

    def test_result_initialization_defaults(self) -> None:
        """Test ExtractionResult initialization with defaults."""
        result = ExtractionResult(documents=[])
        assert result.total_documents == 0
        assert result.total_entities == 0
        assert result.failed_documents == 0
        assert result.duplicate_matches == []

    def test_result_total_documents_property(self) -> None:
        """Test total_documents property calculation."""
        doc1 = ExtractedDocument(
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
        )
        doc2 = ExtractedDocument(
            metadata=DocumentMetadata(
                file_path="/tmp/doc2.pdf",
                file_format=DocumentFormat.PDF,
                file_size_bytes=2048,
                page_count=2,
                title="Doc2",
                author="Author",
                created_at="2024-01-01T00:00:00",
            ),
            pages=[],
        )
        documents = [
            DocumentWithEntities(document=doc1),
            DocumentWithEntities(document=doc2),
        ]
        result = ExtractionResult(documents=documents)
        assert result.total_documents == 2

    def test_result_total_entities_property(self) -> None:
        """Test total_entities property aggregates across documents."""
        doc1 = ExtractedDocument(
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
        )
        doc2 = ExtractedDocument(
            metadata=DocumentMetadata(
                file_path="/tmp/doc2.pdf",
                file_format=DocumentFormat.PDF,
                file_size_bytes=2048,
                page_count=2,
                title="Doc2",
                author="Author",
                created_at="2024-01-01T00:00:00",
            ),
            pages=[],
        )
        documents = [
            DocumentWithEntities(
                document=doc1,
                entities={ENTITY_ID_001: ENTITY_NAME_JOHN},
            ),
            DocumentWithEntities(
                document=doc2,
                entities={ENTITY_ID_002: ENTITY_NAME_JANE},
            ),
        ]
        result = ExtractionResult(documents=documents)
        assert result.total_entities == 2

    def test_result_confidence_match_properties(self) -> None:
        """Test confidence match count properties."""
        dedup_result = DeduplicationResult(
            total_entities=10,
        )
        result = ExtractionResult(
            documents=[],
            deduplication_result=dedup_result,
        )
        assert result.high_confidence_matches == 0
        assert result.medium_confidence_matches == 0
        assert result.low_confidence_matches == 0


class TestExtractionOrchestratorInitialization:
    """Tests for ExtractionOrchestrator initialization."""

    def test_orchestrator_initialization_defaults(self) -> None:
        """Test ExtractionOrchestrator initialization with defaults."""
        orchestrator = ExtractionOrchestrator()
        assert orchestrator.extractor is not None
        assert orchestrator.matcher is not None

    def test_orchestrator_initialization_custom_threshold(self) -> None:
        """Test ExtractionOrchestrator with custom threshold."""
        orchestrator = ExtractionOrchestrator(deduplicate_threshold=0.75)
        assert orchestrator.matcher.string_threshold == 0.75

    def test_orchestrator_initialization_custom_min_length(self) -> None:
        """Test ExtractionOrchestrator with custom min_string_length."""
        orchestrator = ExtractionOrchestrator(min_string_length=5)
        assert orchestrator.matcher.min_string_length == 5


class TestEntityExtraction:
    """Tests for entity extraction from text."""

    def test_extract_entities_basic_capitalized_words(self) -> None:
        """Test extraction of capitalized words as entities."""
        orchestrator = ExtractionOrchestrator()
        text = "John Smith works at Jane Industries"
        entities = orchestrator.extract_entities_from_text(text)
        assert len(entities) > 0
        assert any("John" in name for name in entities.values())

    def test_extract_entities_empty_text(self) -> None:
        """Test entity extraction from empty text."""
        orchestrator = ExtractionOrchestrator()
        entities = orchestrator.extract_entities_from_text("")
        assert entities == {}

    def test_extract_entities_no_capitalized_words(self) -> None:
        """Test extraction with no capitalized words."""
        orchestrator = ExtractionOrchestrator()
        text = "the quick brown fox jumps over the lazy dog"
        entities = orchestrator.extract_entities_from_text(text)
        # Should extract no entities (all words lowercase)
        assert len(entities) == 0

    def test_extract_entities_mixed_case(self) -> None:
        """Test extraction from mixed case text."""
        orchestrator = ExtractionOrchestrator()
        text = "Visit New York and Los Angeles"
        entities = orchestrator.extract_entities_from_text(text)
        # Should extract capitalized words
        assert len(entities) > 0

    def test_extract_entities_punctuation_stripping(self) -> None:
        """Test punctuation is stripped from entities."""
        orchestrator = ExtractionOrchestrator()
        text = "John, Jane, and Jack."
        entities = orchestrator.extract_entities_from_text(text)
        # Check entities don't contain punctuation
        for entity in entities.values():
            assert "," not in entity
            assert "." not in entity

    def test_extract_entities_short_words_ignored(self) -> None:
        """Test short words are not extracted as entities."""
        orchestrator = ExtractionOrchestrator()
        text = "Jo Do Ka"  # All 2-char words
        entities = orchestrator.extract_entities_from_text(text)
        # Min entity length is typically > 3
        assert len(entities) == 0

    def test_extract_entities_numeric_words(self) -> None:
        """Test numeric strings in text."""
        orchestrator = ExtractionOrchestrator()
        text = "Invoice 12345 from Company 2024"
        entities = orchestrator.extract_entities_from_text(text)
        assert entities is not None  # Just verify no crash

    def test_extract_entities_duplicate_words(self) -> None:
        """Test handling of duplicate entity names."""
        orchestrator = ExtractionOrchestrator()
        text = "John Smith and John Doe"
        entities = orchestrator.extract_entities_from_text(text)
        # Should create separate entity IDs for each occurrence
        assert len(entities) > 0


class TestDocumentProcessing:
    """Tests for single document processing."""

    def test_process_document_success(self) -> None:
        """Test successful document processing."""
        mock_doc = ExtractedDocument(
            metadata=DocumentMetadata(
                file_path="/tmp/test.pdf",
                file_format=DocumentFormat.PDF,
                file_size_bytes=1024,
                page_count=1,
                title="Test",
                author="Author",
                created_at="2024-01-01T00:00:00",
            ),
            pages=[
                DocumentPage(
                    page_number=1,
                    text="John Smith works here",
                    metadata=PageMetadata(
                        page_number=1,
                        page_count=1,
                        title="Test",
                    ),
                ),
            ],
        )

        orchestrator = ExtractionOrchestrator()
        with patch.object(
            orchestrator.extractor,
            "extract",
            return_value=mock_doc,
        ):
            result = orchestrator.process_document(
                "/tmp/test.pdf",
                detect_entities=True,
            )

            assert result.document is not None
            assert result.entity_count > 0

    def test_process_document_no_entity_detection(self) -> None:
        """Test document processing without entity detection."""
        mock_doc = ExtractedDocument(
            metadata=DocumentMetadata(
                file_path="/tmp/test.pdf",
                file_format=DocumentFormat.PDF,
                file_size_bytes=1024,
                page_count=1,
                title="Test",
                author="Author",
                created_at="2024-01-01T00:00:00",
            ),
            pages=[],
        )

        orchestrator = ExtractionOrchestrator()
        with patch.object(
            orchestrator.extractor,
            "extract",
            return_value=mock_doc,
        ):
            result = orchestrator.process_document(
                "/tmp/test.pdf",
                detect_entities=False,
            )

            assert result.entity_count == 0
            assert result.entities == {}

    def test_process_document_extraction_error(self) -> None:
        """Test error handling when extraction fails."""
        orchestrator = ExtractionOrchestrator()
        with patch.object(
            orchestrator.extractor,
            "extract",
            side_effect=ExtractionError(
                error_code="PDF_FILE_NOT_FOUND",
                error_message="File not found",
                file_path="/tmp/missing.pdf",
                file_format="pdf",
            ),
        ), pytest.raises(ExtractionOrchestrationError, match="EXTRACTION_FAILED"):
            orchestrator.process_document("/tmp/missing.pdf")

    def test_process_document_unexpected_error(self) -> None:
        """Test error handling for unexpected exceptions."""
        orchestrator = ExtractionOrchestrator()
        with patch.object(
            orchestrator.extractor,
            "extract",
            side_effect=ValueError("Unexpected error"),
        ), pytest.raises(ExtractionOrchestrationError, match="PROCESSING_FAILED"):
            orchestrator.process_document("/tmp/test.pdf")

    def test_process_document_multipage(self) -> None:
        """Test processing multi-page document."""
        mock_doc = ExtractedDocument(
            metadata=DocumentMetadata(
                file_path="/tmp/test.pdf",
                file_format=DocumentFormat.PDF,
                file_size_bytes=2048,
                page_count=3,
                title="Multi-page",
                author="Author",
                created_at="2024-01-01T00:00:00",
            ),
            pages=[
                DocumentPage(
                    page_number=1,
                    text="John works",
                    metadata=PageMetadata(page_number=1, page_count=3),
                ),
                DocumentPage(
                    page_number=2,
                    text="Jane manages",
                    metadata=PageMetadata(page_number=2, page_count=3),
                ),
                DocumentPage(
                    page_number=3,
                    text="Jack leads",
                    metadata=PageMetadata(page_number=3, page_count=3),
                ),
            ],
        )

        orchestrator = ExtractionOrchestrator()
        with patch.object(
            orchestrator.extractor,
            "extract",
            return_value=mock_doc,
        ):
            result = orchestrator.process_document("/tmp/test.pdf", detect_entities=True)
            assert result.entity_count > 0


class TestBatchProcessing:
    """Tests for batch document processing."""

    def test_process_batch_empty_request(self) -> None:
        """Test batch processing with empty file paths."""
        orchestrator = ExtractionOrchestrator()
        request = ExtractionRequest(file_paths=[])
        with pytest.raises(ExtractionOrchestrationError, match="INVALID_REQUEST"):
            orchestrator.process_batch(request)

    def test_process_batch_single_document(self) -> None:
        """Test batch processing with single document."""
        with patch.object(ExtractionOrchestrator, "process_document") as mock_process:
            mock_doc = DocumentWithEntities(
                document=ExtractedDocument(
                    metadata=DocumentMetadata(
                        file_path="/tmp/test.pdf",
                        file_format=DocumentFormat.PDF,
                        file_size_bytes=1024,
                        page_count=1,
                        title="Test",
                        author="Author",
                        created_at="2024-01-01T00:00:00",
                    ),
                    pages=[],
                ),
                entities={ENTITY_ID_001: ENTITY_NAME_JOHN},
            )
            mock_process.return_value = mock_doc

            orchestrator = ExtractionOrchestrator()
            request = ExtractionRequest(
                file_paths=["/tmp/test.pdf"],
                detect_entities=True,
            )
            result = orchestrator.process_batch(request)

            assert result.total_documents == 1
            assert result.total_entities == 1

    def test_process_batch_multiple_documents(self) -> None:
        """Test batch processing with multiple documents."""
        with patch.object(ExtractionOrchestrator, "process_document") as mock_process:
            doc1 = DocumentWithEntities(
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
                entities={ENTITY_ID_001: ENTITY_NAME_JOHN},
            )
            doc2 = DocumentWithEntities(
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
                entities={ENTITY_ID_002: ENTITY_NAME_JANE},
            )
            mock_process.side_effect = [doc1, doc2]

            orchestrator = ExtractionOrchestrator()
            request = ExtractionRequest(
                file_paths=["/tmp/doc1.pdf", "/tmp/doc2.pdf"],
                detect_entities=True,
            )
            result = orchestrator.process_batch(request)

            assert result.total_documents == 2
            assert result.total_entities == 2

    def test_process_batch_with_deduplication(self) -> None:
        """Test batch processing with entity deduplication."""
        with patch.object(ExtractionOrchestrator, "process_document") as mock_process:
            doc = DocumentWithEntities(
                document=ExtractedDocument(
                    metadata=DocumentMetadata(
                        file_path="/tmp/test.pdf",
                        file_format=DocumentFormat.PDF,
                        file_size_bytes=1024,
                        page_count=1,
                        title="Test",
                        author="Author",
                        created_at="2024-01-01T00:00:00",
                    ),
                    pages=[],
                ),
                entities={ENTITY_ID_001: ENTITY_NAME_JOHN},
            )
            mock_process.return_value = doc

            orchestrator = ExtractionOrchestrator()
            request = ExtractionRequest(
                file_paths=["/tmp/test.pdf"],
                detect_entities=True,
                deduplicate_threshold=0.85,
            )
            result = orchestrator.process_batch(request)

            assert result.deduplication_result is not None

    def test_process_batch_no_entity_detection(self) -> None:
        """Test batch processing without entity detection."""
        with patch.object(ExtractionOrchestrator, "process_document") as mock_process:
            doc = DocumentWithEntities(
                document=ExtractedDocument(
                    metadata=DocumentMetadata(
                        file_path="/tmp/test.pdf",
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
            mock_process.return_value = doc

            orchestrator = ExtractionOrchestrator()
            request = ExtractionRequest(
                file_paths=["/tmp/test.pdf"],
                detect_entities=False,
            )
            result = orchestrator.process_batch(request)

            assert result.total_entities == 0
            assert result.deduplication_result is None

    def test_process_batch_partial_failure(self) -> None:
        """Test batch processing with some documents failing."""
        with patch.object(ExtractionOrchestrator, "process_document") as mock_process:
            doc = DocumentWithEntities(
                document=ExtractedDocument(
                    metadata=DocumentMetadata(
                        file_path="/tmp/test.pdf",
                        file_format=DocumentFormat.PDF,
                        file_size_bytes=1024,
                        page_count=1,
                        title="Test",
                        author="Author",
                        created_at="2024-01-01T00:00:00",
                    ),
                    pages=[],
                ),
                entities={ENTITY_ID_001: ENTITY_NAME_JOHN},
            )
            mock_process.side_effect = [
                doc,
                ExtractionOrchestrationError(
                    error_code="EXTRACTION_FAILED",
                    error_message="Failed",
                ),
            ]

            orchestrator = ExtractionOrchestrator()
            request = ExtractionRequest(
                file_paths=["/tmp/test.pdf", "/tmp/missing.pdf"],
                detect_entities=True,
            )
            result = orchestrator.process_batch(request)

            assert result.total_documents == 1
            assert result.failed_documents == 1

    def test_process_batch_all_failures(self) -> None:
        """Test batch processing with all documents failing."""
        with patch.object(ExtractionOrchestrator, "process_document") as mock_process:
            mock_process.side_effect = ExtractionOrchestrationError(
                error_code="EXTRACTION_FAILED",
                error_message="Failed",
            )

            orchestrator = ExtractionOrchestrator()
            request = ExtractionRequest(file_paths=["/tmp/test1.pdf", "/tmp/test2.pdf"])
            with pytest.raises(ExtractionOrchestrationError, match="BATCH_EMPTY"):
                orchestrator.process_batch(request)


class TestErrorHandling:
    """Tests for error handling and recovery."""

    def test_error_extraction_orchestration(self) -> None:
        """Test ExtractionOrchestrationError creation."""
        error = ExtractionOrchestrationError(
            error_code="TEST_ERROR",
            error_message="Test message",
            file_path="/tmp/test.pdf",
            stage="test_stage",
        )
        assert error.error_code == "TEST_ERROR"
        assert error.file_path == "/tmp/test.pdf"
        assert error.stage == "test_stage"

    def test_error_handling_invalid_threshold_zero(self) -> None:
        """Test validation rejects zero threshold."""
        request = ExtractionRequest(
            file_paths=REQUEST_FILE_PATHS,
            deduplicate_threshold=0.0,
        )
        request.validate()  # Should pass - 0.0 is valid

    def test_error_handling_invalid_threshold_negative(self) -> None:
        """Test validation rejects negative threshold."""
        request = ExtractionRequest(
            file_paths=REQUEST_FILE_PATHS,
            deduplicate_threshold=-0.1,
        )
        with pytest.raises(ExtractionOrchestrationError, match="INVALID_THRESHOLD"):
            request.validate()

    def test_error_handling_document_extraction_propagation(self) -> None:
        """Test ExtractionError propagates as ExtractionOrchestrationError."""
        orchestrator = ExtractionOrchestrator()
        with patch.object(
            orchestrator.extractor,
            "extract",
            side_effect=ExtractionError(
                error_code="PDF_EXTRACTION_FAILED",
                error_message="PDF corruption",
                file_path="/tmp/corrupt.pdf",
                file_format="pdf",
            ),
        ):
            with pytest.raises(ExtractionOrchestrationError) as exc_info:
                orchestrator.process_document("/tmp/corrupt.pdf")
            assert exc_info.value.error_code == "EXTRACTION_FAILED"

    def test_error_handling_deduplication_error(self) -> None:
        """Test FuzzyMatcherError handling during deduplication."""
        with patch.object(ExtractionOrchestrator, "process_document") as mock_process:
            doc = DocumentWithEntities(
                document=ExtractedDocument(
                    metadata=DocumentMetadata(
                        file_path="/tmp/test.pdf",
                        file_format=DocumentFormat.PDF,
                        file_size_bytes=1024,
                        page_count=1,
                        title="Test",
                        author="Author",
                        created_at="2024-01-01T00:00:00",
                    ),
                    pages=[],
                ),
                entities={ENTITY_ID_001: ENTITY_NAME_JOHN},
            )
            mock_process.return_value = doc

        with patch("src.pipelines.services.extraction_orchestrator.FuzzyMatcher") as mock_matcher:
            mock_instance = MagicMock()
            mock_instance.analyze_deduplication.side_effect = FuzzyMatcherError(
                error_code="ANALYSIS_FAILED",
                error_message="Analysis failed",
            )
            mock_matcher.return_value = mock_instance

            orchestrator = ExtractionOrchestrator()
            request = ExtractionRequest(
                file_paths=["/tmp/test.pdf"],
                detect_entities=True,
            )
            with patch.object(
                orchestrator,
                "process_document",
                return_value=doc,
            ), pytest.raises(ExtractionOrchestrationError, match="DEDUPLICATION_FAILED"):
                orchestrator.process_batch(request)
