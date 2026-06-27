"""Unified REST API for document extraction and entity deduplication.

This module provides production-grade FastAPI endpoints for the complete
memory graph ingestion pipeline:

Endpoints:
  POST /api/v1/extract/document - Extract single document
  POST /api/v1/extract/batch - Batch extract documents
  POST /api/v1/deduplicate - Deduplicate entities
  GET /api/v1/health - Health check

Architecture:
  - FastAPI application with OpenAPI documentation
  - Request/response validation with Pydantic
  - Structured error handling with standard error codes
  - Comprehensive logging and observability
  - Production-ready async/await support
"""

from __future__ import annotations

import logging
from http import HTTPStatus

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.pipelines.services.extraction_orchestrator import (
    ExtractionOrchestrationError,
    ExtractionOrchestrator,
    ExtractionRequest,
)

logger = logging.getLogger(__name__)

# API version for versioned endpoints
API_VERSION = "v1"


# Request/Response Models for API
class DocumentExtractionRequest(BaseModel):
    """Request model for single document extraction.

    Attributes:
        file_path: Path to document file (PDF/PPTX).
        detect_entities: Whether to extract entities from document.
    """

    file_path: str = Field(..., description="Path to document file")
    detect_entities: bool = Field(
        default=True,
        description="Whether to extract entities from document",
    )


class DocumentExtractionResponse(BaseModel):
    """Response model for successful document extraction.

    Attributes:
        success: Whether extraction succeeded.
        file_path: Path to extracted document.
        page_count: Total pages/slides in document.
        entity_count: Total entities extracted from document.
        message: Informational message.
    """

    success: bool = Field(default=True, description="Extraction success status")
    file_path: str = Field(description="Extracted document path")
    page_count: int = Field(description="Total document pages")
    entity_count: int = Field(description="Total entities extracted")
    message: str = Field(default="Document extracted successfully")


class BatchExtractionRequest(BaseModel):
    """Request model for batch document extraction.

    Attributes:
        file_paths: List of document paths.
        detect_entities: Whether to extract entities.
        deduplicate_threshold: Entity similarity threshold (0.0-1.0).
        include_low_confidence_matches: Include low-confidence duplicates.
    """

    file_paths: list[str] = Field(..., description="List of document paths")
    detect_entities: bool = Field(
        default=True,
        description="Whether to extract entities",
    )
    deduplicate_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Entity deduplication threshold",
    )
    include_low_confidence_matches: bool = Field(
        default=False,
        description="Include low-confidence duplicate matches",
    )


class BatchExtractionResponse(BaseModel):
    """Response model for batch extraction results.

    Attributes:
        success: Whether batch processing succeeded.
        total_documents: Total successfully processed documents.
        failed_documents: Number of failed documents.
        total_entities: Total unique entities across all documents.
        high_confidence_matches: Count of high-confidence duplicates.
        medium_confidence_matches: Count of medium-confidence duplicates.
        low_confidence_matches: Count of low-confidence duplicates.
        message: Informational message.
    """

    success: bool = Field(default=True, description="Batch processing status")
    total_documents: int = Field(description="Successfully processed documents")
    failed_documents: int = Field(description="Failed documents")
    total_entities: int = Field(description="Total unique entities")
    high_confidence_matches: int = Field(
        description="High-confidence duplicate matches",
    )
    medium_confidence_matches: int = Field(
        description="Medium-confidence duplicate matches",
    )
    low_confidence_matches: int = Field(
        description="Low-confidence duplicate matches",
    )
    message: str = Field(default="Batch processing completed successfully")


class ErrorResponse(BaseModel):
    """Standard error response model.

    Attributes:
        success: Always False for error responses.
        error_code: Machine-readable error code.
        error_message: Human-readable error message.
        detail: Additional error details (optional).
    """

    success: bool = Field(default=False, description="Error status")
    error_code: str = Field(description="Machine-readable error code")
    error_message: str = Field(description="Human-readable error message")
    detail: str | None = Field(default=None, description="Additional error details")


class HealthCheckResponse(BaseModel):
    """Health check response model.

    Attributes:
        status: Service status ("healthy" or "unhealthy").
        message: Status message.
        api_version: Current API version.
    """

    status: str = Field(description="Service health status")
    message: str = Field(description="Status message")
    api_version: str = Field(description="API version")


# Initialize FastAPI application
app = FastAPI(
    title="Document Extraction & Entity Deduplication API",
    description="Unified API for memory graph ingestion pipeline",
    version=API_VERSION,
)

# Initialize orchestrator
orchestrator = ExtractionOrchestrator()


@app.get("/api/v1/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Health check endpoint.

    Returns:
        HealthCheckResponse: Service health status.
    """
    logger.debug("Health check request")
    return HealthCheckResponse(
        status="healthy",
        message="Service is running",
        api_version=API_VERSION,
    )


@app.post(
    "/api/v1/extract/document",
    response_model=DocumentExtractionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def extract_document(
    request: DocumentExtractionRequest,
) -> DocumentExtractionResponse:
    """Extract text and entities from a single document.

    Args:
        request: Document extraction request.

    Returns:
        DocumentExtractionResponse: Extraction results.

    Raises:
        HTTPException: If extraction fails.
    """
    logger.info("Document extraction request: %s", request.file_path)

    try:
        doc_with_entities = orchestrator.process_document(
            request.file_path,
            detect_entities=request.detect_entities,
        )

        response = DocumentExtractionResponse(
            file_path=request.file_path,
            page_count=doc_with_entities.document.metadata.page_count,
            entity_count=doc_with_entities.entity_count,
        )

        logger.info(
            "Document extraction successful: %s (%d entities)",
            request.file_path,
            doc_with_entities.entity_count,
        )

        return response  # noqa: TRY300

    except ExtractionOrchestrationError as e:
        logger.exception(
            "Document extraction failed: %s (code: %s)",
            e.error_message,
            e.error_code,
        )
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=ErrorResponse(
                error_code=e.error_code,
                error_message=e.error_message,
                detail=f"File: {e.file_path}",
            ).model_dump(),
        ) from e

    except Exception as e:
        logger.exception("Unexpected error during document extraction")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code="INTERNAL_ERROR",
                error_message="Unexpected error during extraction",
                detail=str(e),
            ).model_dump(),
        ) from e


@app.post(
    "/api/v1/extract/batch",
    response_model=BatchExtractionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def extract_batch(
    request: BatchExtractionRequest,
) -> BatchExtractionResponse:
    """Process batch of documents with entity deduplication.

    Args:
        request: Batch extraction request.

    Returns:
        BatchExtractionResponse: Batch processing results.

    Raises:
        HTTPException: If batch processing fails.
    """
    logger.info(
        "Batch extraction request: %d documents, threshold=%.2f",
        len(request.file_paths),
        request.deduplicate_threshold,
    )

    try:
        # Create extraction request
        extraction_request = ExtractionRequest(
            file_paths=request.file_paths,
            detect_entities=request.detect_entities,
            deduplicate_threshold=request.deduplicate_threshold,
            include_low_confidence_matches=request.include_low_confidence_matches,
        )

        # Process batch
        result = orchestrator.process_batch(extraction_request)

        response = BatchExtractionResponse(
            total_documents=result.total_documents,
            failed_documents=result.failed_documents,
            total_entities=result.total_entities,
            high_confidence_matches=result.high_confidence_matches,
            medium_confidence_matches=result.medium_confidence_matches,
            low_confidence_matches=result.low_confidence_matches,
        )

        logger.info(
            "Batch processing successful: %d docs, %d entities, "
            "%d matches (HIGH: %d, MEDIUM: %d, LOW: %d)",
            result.total_documents,
            result.total_entities,
            len(result.duplicate_matches),
            result.high_confidence_matches,
            result.medium_confidence_matches,
            result.low_confidence_matches,
        )

        return response  # noqa: TRY300

    except ExtractionOrchestrationError as e:
        logger.exception(
            "Batch processing failed: %s (code: %s, stage: %s)",
            e.error_message,
            e.error_code,
            e.stage,
        )
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=ErrorResponse(
                error_code=e.error_code,
                error_message=e.error_message,
                detail=f"Stage: {e.stage}",
            ).model_dump(),
        ) from e

    except Exception as e:
        logger.exception("Unexpected error during batch processing")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code="INTERNAL_ERROR",
                error_message="Unexpected error during batch processing",
                detail=str(e),
            ).model_dump(),
        ) from e


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API information.

    Returns:
        dict: API information and version.
    """
    return {
        "name": "Document Extraction & Entity Deduplication API",
        "version": API_VERSION,
        "docs": "/docs",
    }
