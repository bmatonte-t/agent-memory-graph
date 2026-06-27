"""Orchestrates document extraction and entity deduplication pipeline.

This module provides a unified service that:
1. Extracts text and metadata from documents (PDF/PPTX)
2. Identifies entities from extracted content
3. Deduplicates entities using fuzzy matching
4. Returns structured results for downstream processing

Architecture:
  - ExtractionRequest: Input specification for document batch processing
  - ExtractionResult: Output containing documents, entities, and deduplication metrics
  - ExtractionOrchestrator: Main service class orchestrating the pipeline
  - ExtractionError: Custom exception for pipeline failures

Typical usage:
  orchestrator = ExtractionOrchestrator()
  request = ExtractionRequest(
      file_paths=["/tmp/doc1.pdf", "/tmp/doc2.pptx"],
      detect_entities=True,
      deduplicate_threshold=0.85,
  )
  result = orchestrator.process_batch(request)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.pipelines.document_ingestion.document_extractor import (
    DocumentExtractor,
    ExtractedDocument,
    ExtractionError,
)
from src.pipelines.entity_linking.fuzzy_matcher import (
    DeduplicationResult,
    FuzzyMatcher,
    FuzzyMatcherError,
    MatchCandidate,
)

logger = logging.getLogger(__name__)

# Minimum entity name length for extraction
MIN_ENTITY_LENGTH = 3


class ExtractionOrchestrationError(Exception):
    """Custom exception for extraction orchestration failures.

    Attributes:
        error_code: Unique error identifier for categorization.
        error_message: Human-readable error description.
        file_path: Path to the document that caused the error (optional).
        stage: Pipeline stage where error occurred (optional).
    """

    def __init__(
        self,
        error_code: str,
        error_message: str,
        file_path: str | None = None,
        stage: str | None = None,
    ) -> None:
        """Initialize ExtractionOrchestrationError.

        Args:
            error_code: Error category (e.g., "EXTRACTION_FAILED").
            error_message: Detailed error description.
            file_path: Path to problematic document (optional).
            stage: Pipeline stage identifier (optional).
        """
        self.error_code = error_code
        self.error_message = error_message
        self.file_path = file_path
        self.stage = stage
        super().__init__(f"[{error_code}] {error_message}")


@dataclass
class ExtractionRequest:
    """Request specification for batch document extraction.

    Attributes:
        file_paths: List of document paths (PDF/PPTX formats).
        detect_entities: Whether to extract entities from documents.
        deduplicate_threshold: Similarity threshold for deduplication (0.0-1.0).
        include_low_confidence_matches: Include low-confidence dedup matches.
        min_string_length: Minimum entity name length for matching.
    """

    file_paths: list[str]
    detect_entities: bool = True
    deduplicate_threshold: float = 0.85
    include_low_confidence_matches: bool = False
    min_string_length: int = 3

    def validate(self) -> None:
        """Validate request parameters.

        Raises:
            ExtractionOrchestrationError: If validation fails.
        """
        if not self.file_paths:
            msg = "file_paths cannot be empty"
            raise ExtractionOrchestrationError(
                error_code="INVALID_REQUEST",
                error_message=msg,
            )

        if not 0.0 <= self.deduplicate_threshold <= 1.0:
            msg = f"deduplicate_threshold must be 0.0-1.0, got {self.deduplicate_threshold}"
            raise ExtractionOrchestrationError(
                error_code="INVALID_THRESHOLD",
                error_message=msg,
            )

        if self.min_string_length < 1:
            msg = f"min_string_length must be >= 1, got {self.min_string_length}"
            raise ExtractionOrchestrationError(
                error_code="INVALID_MIN_LENGTH",
                error_message=msg,
            )


@dataclass
class DocumentWithEntities:
    """Extracted document with identified entities.

    Attributes:
        document: Extracted document with text and metadata.
        entities: Dict mapping entity_id to entity_name.
        entity_count: Total number of entities extracted.
    """

    document: ExtractedDocument
    entities: dict[str, str] = field(default_factory=dict)
    entity_count: int = 0

    def __post_init__(self) -> None:
        """Post-initialization validation."""
        self.entity_count = len(self.entities)


@dataclass
class ExtractionResult:
    """Result of batch document extraction with deduplication.

    Attributes:
        documents: List of extracted documents with entities.
        deduplication_result: Entity deduplication metrics and matches.
        total_documents: Number of successfully processed documents.
        failed_documents: Number of failed documents.
        total_entities: Total unique entities across all documents.
        duplicate_matches: List of potential duplicate matches.
    """

    documents: list[DocumentWithEntities]
    deduplication_result: DeduplicationResult | None = None
    failed_documents: int = 0
    duplicate_matches: list[MatchCandidate] = field(default_factory=list)

    @property
    def total_documents(self) -> int:
        """Return total successfully processed documents."""
        return len(self.documents)

    @property
    def total_entities(self) -> int:
        """Return total unique entities across all documents."""
        all_entities = {}
        for doc in self.documents:
            all_entities.update(doc.entities)
        return len(all_entities)

    @property
    def high_confidence_matches(self) -> int:
        """Return count of high-confidence duplicate matches."""
        if self.deduplication_result is None:
            return 0
        return self.deduplication_result.high_confidence_count

    @property
    def medium_confidence_matches(self) -> int:
        """Return count of medium-confidence duplicate matches."""
        if self.deduplication_result is None:
            return 0
        return self.deduplication_result.medium_confidence_count

    @property
    def low_confidence_matches(self) -> int:
        """Return count of low-confidence duplicate matches."""
        if self.deduplication_result is None:
            return 0
        return self.deduplication_result.low_confidence_count


class ExtractionOrchestrator:
    """Orchestrates document extraction and entity deduplication pipeline.

    Combines DocumentExtractor for text extraction with FuzzyMatcher for
    entity deduplication into a unified, production-grade service.

    Attributes:
        extractor: DocumentExtractor instance for PDF/PPTX processing.
        matcher: FuzzyMatcher instance for entity deduplication.
    """

    def __init__(
        self,
        deduplicate_threshold: float = 0.85,
        min_string_length: int = 3,
    ) -> None:
        """Initialize ExtractionOrchestrator.

        Args:
            deduplicate_threshold: Similarity threshold for deduplication.
            min_string_length: Minimum entity name length for matching.
        """
        self.extractor = DocumentExtractor()
        self.matcher = FuzzyMatcher(
            string_threshold=deduplicate_threshold,
            min_string_length=min_string_length,
        )
        logger.info(
            "Initialized ExtractionOrchestrator (threshold=%s, min_length=%d)",
            deduplicate_threshold,
            min_string_length,
        )

    def extract_entities_from_text(
        self,
        text: str,
    ) -> dict[str, str]:
        """Extract entities from raw text content.

        Current implementation uses naive word-based extraction.
        Future: Integrate LLM-based NER for production entity extraction.

        Args:
            text: Raw text content from document.

        Returns:
            dict[str, str]: Mapping of entity_id to entity_name.
        """
        entities = {}
        # Naive extraction: split by whitespace and filter
        words = text.split()
        entity_id = 0

        for word in words:
            # Simple heuristic: entities are capitalized words (>MIN_ENTITY_LENGTH chars)
            if len(word) > MIN_ENTITY_LENGTH and word[0].isupper():
                entity_id_str = f"entity_{entity_id:04d}"
                entities[entity_id_str] = word.strip(".,;:!?")
                entity_id += 1

        logger.debug("Extracted %d entities from text (%d words)", len(entities), len(words))
        return entities

    def process_document(
        self,
        file_path: str,
        *,
        detect_entities: bool = True,
    ) -> DocumentWithEntities:
        """Process a single document through extraction pipeline.

        Args:
            file_path: Path to document file.
            detect_entities: Whether to extract entities from document.

        Returns:
            DocumentWithEntities: Extracted document with entities.

        Raises:
            ExtractionOrchestrationError: If extraction fails.
        """
        try:
            # Step 1: Extract text and metadata
            extracted_doc = self.extractor.extract(file_path)

            # Step 2: Extract entities if requested
            entities: dict[str, str] = {}
            if detect_entities:
                combined_text = " ".join(page.text for page in extracted_doc.pages)
                entities = self.extract_entities_from_text(combined_text)

            result = DocumentWithEntities(
                document=extracted_doc,
                entities=entities,
            )

            logger.info(
                "Processed document: %s (%d entities, %d pages)",
                file_path,
                len(entities),
                extracted_doc.metadata.page_count,
            )

            return result  # noqa: TRY300

        except ExtractionError as e:
            msg = f"Document extraction failed: {e.error_message}"
            logger.exception(msg)
            raise ExtractionOrchestrationError(
                error_code="EXTRACTION_FAILED",
                error_message=msg,
                file_path=file_path,
                stage="extraction",
            ) from e
        except Exception as e:
            msg = f"Unexpected error during document processing: {e!s}"
            logger.exception(msg)
            raise ExtractionOrchestrationError(
                error_code="PROCESSING_FAILED",
                error_message=msg,
                file_path=file_path,
                stage="processing",
            ) from e

    def process_batch(
        self,
        request: ExtractionRequest,
    ) -> ExtractionResult:
        """Process batch of documents through extraction and deduplication.

        Pipeline stages:
        1. Validate request parameters
        2. Extract each document individually
        3. Combine entities across all documents
        4. Deduplicate entities using fuzzy matching
        5. Return structured results

        Args:
            request: Batch extraction request specification.

        Returns:
            ExtractionResult: Aggregated extraction and deduplication results.

        Raises:
            ExtractionOrchestrationError: If batch processing fails.
        """
        try:
            # Stage 1: Validate request
            request.validate()
            logger.info("Processing batch of %d documents", len(request.file_paths))

            # Stage 2: Extract documents
            documents: list[DocumentWithEntities] = []
            failed_count = 0

            for file_path in request.file_paths:
                try:
                    doc = self.process_document(
                        file_path,
                        detect_entities=request.detect_entities,
                    )
                    documents.append(doc)
                except ExtractionOrchestrationError as e:
                    logger.warning("Failed to process document: %s (%s)", file_path, e.error_code)
                    failed_count += 1

            if not documents:
                msg = "No documents successfully extracted from batch"
                logger.error(msg)
                raise ExtractionOrchestrationError(  # noqa: TRY301
                    error_code="BATCH_EMPTY",
                    error_message=msg,
                    stage="batch_processing",
                )

            # Stage 3: Combine entities
            all_entities = {}
            for doc in documents:
                all_entities.update(doc.entities)

            # Stage 4: Deduplicate entities if requested and entities exist
            dedup_result = None
            duplicate_matches: list[MatchCandidate] = []

            if request.detect_entities and all_entities:
                try:
                    # Create matcher with request threshold
                    matcher = FuzzyMatcher(
                        string_threshold=request.deduplicate_threshold,
                        min_string_length=request.min_string_length,
                    )

                    # Analyze deduplication
                    dedup_result = matcher.analyze_deduplication(
                        all_entities,
                        include_low_confidence=request.include_low_confidence_matches,
                    )

                    # Get duplicate matches
                    candidates = matcher.find_candidates(all_entities)
                    duplicate_matches = matcher.filter_by_confidence(
                        candidates,
                        min_confidence="MEDIUM",
                    )

                    logger.info(
                        "Deduplication complete: %d matches found (%d HIGH, %d MEDIUM, %d LOW)",
                        len(duplicate_matches),
                        dedup_result.high_confidence_count,
                        dedup_result.medium_confidence_count,
                        dedup_result.low_confidence_count,
                    )

                except FuzzyMatcherError as e:
                    msg = f"Entity deduplication failed: {e.error_message}"
                    logger.exception(msg)
                    raise ExtractionOrchestrationError(
                        error_code="DEDUPLICATION_FAILED",
                        error_message=msg,
                        stage="deduplication",
                    ) from e

            # Stage 5: Build result
            result = ExtractionResult(
                documents=documents,
                deduplication_result=dedup_result,
                failed_documents=failed_count,
                duplicate_matches=duplicate_matches,
            )

            logger.info(
                "Batch processing complete: %d succeeded, %d failed, %d total entities, "
                "%d duplicate matches",
                result.total_documents,
                result.failed_documents,
                result.total_entities,
                len(result.duplicate_matches),
            )

            return result  # noqa: TRY300

        except ExtractionOrchestrationError:
            raise
        except Exception as e:
            msg = f"Batch processing failed: {e!s}"
            logger.exception(msg)
            raise ExtractionOrchestrationError(
                error_code="BATCH_PROCESSING_FAILED",
                error_message=msg,
                stage="batch_processing",
            ) from e
