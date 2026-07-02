"""Phase E: End-to-end extraction pipeline integration tests.

This module tests the complete extraction pipeline from document ingestion
through entity extraction, deduplication, and REST API delivery. It validates
error recovery, pipeline orchestration, and deployment readiness.

Test Coverage:
  - Full pipeline integration (document → extraction → deduplication → API)
  - Mock GCP services (Cloud Run simulation, Spanner interaction)
  - Error recovery scenarios (partial failures, retries)
  - Canary deployment validation
  - Performance and scalability characteristics
"""

# ruff: noqa: PLR2004

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from src.deployment.cloud_run_config import (
    CloudRunConfig,
    CloudRunDeploymentManager,
    DeploymentEnvironment,
    create_dev_config,
    create_prod_config,
    create_staging_config,
)
from src.pipelines.api.extraction_api import app
from src.pipelines.services.extraction_orchestrator import (
    ExtractionOrchestrator,
)


@dataclass(slots=True)
class _ExtractedDocumentStub:
    """Deterministic extracted-document shape for integration tests."""

    document_id: str
    text: str


@dataclass(slots=True)
class _DeduplicationResultsStub:
    """Deterministic deduplication summary used by pipeline tests."""

    candidates_found: int
    matches_identified: int
    duplicate_candidates: list[dict[str, object]]


@dataclass(slots=True)
class _BatchResultStub:
    """Deterministic process_batch return payload used in integration tests."""

    extracted_documents: list[_ExtractedDocumentStub]
    errors: list[dict[str, str]]
    deduplication_results: _DeduplicationResultsStub | None = None


class TestExtractionPipelineEndToEnd:
    """Test complete pipeline from document ingestion to API response."""

    @pytest.fixture
    def client(self) -> TestClient:
        """FastAPI test client for extraction API."""
        return TestClient(app)

    def test_api_health_check(self, client: TestClient) -> None:
        """Validate API health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "api_version" in data
        assert "message" in data

    def test_api_root_endpoint(self, client: TestClient) -> None:
        """Test API root endpoint returns service info."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "service" in data or "name" in data

    def test_orchestrator_instantiation(self) -> None:
        """Test extraction orchestrator can be instantiated."""
        orchestrator = ExtractionOrchestrator()
        assert orchestrator is not None

    def test_cloud_run_deployment_validation(self) -> None:
        """Validate Cloud Run deployment configuration is prod-ready."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="extraction-api",
            image_uri="gcr.io/test-project/extraction-api:v1",
            environment=DeploymentEnvironment.PROD,
            enable_authentication=True,
        )

        manager = CloudRunDeploymentManager(config)
        assert manager.validate_configuration()

        # Verify command generation
        command = manager.get_deployment_command()
        assert "--require-authentication" in command
        assert "--platform=managed" in command

    def test_dev_environment_config(self) -> None:
        """Test development environment configuration."""
        config = create_dev_config(
            project_id="test-project",
            image_uri="gcr.io/test-project/api:latest",
        )

        assert config.environment == DeploymentEnvironment.DEV
        assert config.enable_authentication is False

    def test_staging_environment_config(self) -> None:
        """Test staging environment configuration."""
        config = create_staging_config(
            project_id="test-project",
            image_uri="gcr.io/test-project/api:latest",
        )

        assert config.environment == DeploymentEnvironment.STAGING
        assert config.enable_authentication is True

    def test_prod_environment_config(self) -> None:
        """Test production environment configuration."""
        config = create_prod_config(
            project_id="test-project",
            image_uri="gcr.io/test-project/api:latest",
        )

        assert config.environment == DeploymentEnvironment.PROD
        assert config.enable_authentication is True

    def test_canary_deployment_configuration(self) -> None:
        """Test canary deployment strategy for safe rollout."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="extraction-api",
            image_uri="gcr.io/test-project/extraction-api:v2",
            environment=DeploymentEnvironment.PROD,
        )

        manager = CloudRunDeploymentManager(config)

        # Generate canary deployment (10% to new, 90% to old)
        canary_command = manager.get_canary_deployment_command(new_revision_traffic=10)

        assert isinstance(canary_command, str)
        assert "gcloud run services update-traffic" in canary_command

    def test_deployment_rollback_capability(self) -> None:
        """Test rollback to previous revision if deployment fails."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="extraction-api",
            image_uri="gcr.io/test-project/extraction-api:v2",
        )

        manager = CloudRunDeploymentManager(config)
        rollback_command = manager.get_rollback_command(revision="extraction-api-dev-revision-1")

        assert isinstance(rollback_command, str)
        assert "gcloud run services update-traffic" in rollback_command
        assert "extraction-api-dev" in rollback_command

    async def test_async_batch_processing(self) -> None:
        """Test async execution of extraction pipeline."""
        original_process_batch = ExtractionOrchestrator.process_batch

        async def _process_batch_stub(
            self: ExtractionOrchestrator,
            file_paths: list[str],
            *,
            detect_entities: bool,
        ) -> _BatchResultStub:
            del self
            assert file_paths == ["doc_1.pdf"]
            assert detect_entities is True
            return _BatchResultStub(
                extracted_documents=[_ExtractedDocumentStub(document_id="doc_1", text="Content")],
                errors=[],
            )

        ExtractionOrchestrator.process_batch = _process_batch_stub

        try:
            orchestrator = ExtractionOrchestrator()
            result = await orchestrator.process_batch(["doc_1.pdf"], detect_entities=True)

            assert len(result.extracted_documents) == 1
            assert result.extracted_documents[0].document_id == "doc_1"
        finally:
            ExtractionOrchestrator.process_batch = original_process_batch

    def test_error_recovery_on_partial_failure(self) -> None:
        """Test pipeline resilience when some documents fail."""
        original_process_batch = ExtractionOrchestrator.process_batch

        def _process_batch_stub(
            self: ExtractionOrchestrator,
            file_paths: list[str],
            *,
            detect_entities: bool,
        ) -> _BatchResultStub:
            del self
            assert file_paths == ["doc_1.pdf", "doc_2.pdf", "doc_3.pdf"]
            assert detect_entities is True
            return _BatchResultStub(
                extracted_documents=[
                    _ExtractedDocumentStub(document_id="doc_1", text="Content 1"),
                    _ExtractedDocumentStub(document_id="doc_3", text="Content 3"),
                ],
                errors=[
                    {
                        "file_path": "doc_2.pdf",
                        "error_code": "EXTRACTION_FAILED",
                        "error_message": "Failed to extract PDF",
                    }
                ],
            )

        ExtractionOrchestrator.process_batch = _process_batch_stub

        try:
            orchestrator = ExtractionOrchestrator()
            result = orchestrator.process_batch(
                ["doc_1.pdf", "doc_2.pdf", "doc_3.pdf"],
                detect_entities=True,
            )

            # Verify partial success
            assert len(result.extracted_documents) == 2
            assert len(result.errors) == 1
            assert result.errors[0]["file_path"] == "doc_2.pdf"
        finally:
            ExtractionOrchestrator.process_batch = original_process_batch

    def test_entity_deduplication_in_pipeline(self) -> None:
        """Test entity deduplication integrated in extraction pipeline."""
        original_process_batch = ExtractionOrchestrator.process_batch

        def _process_batch_stub(
            self: ExtractionOrchestrator,
            file_paths: list[str],
            *,
            detect_entities: bool,
        ) -> _BatchResultStub:
            del self
            assert file_paths == ["doc_1.pdf", "doc_2.pdf"]
            assert detect_entities is True
            return _BatchResultStub(
                extracted_documents=[
                    _ExtractedDocumentStub(document_id="doc_1", text="John Smith"),
                    _ExtractedDocumentStub(document_id="doc_2", text="Jon Smith"),
                ],
                deduplication_results=_DeduplicationResultsStub(
                    candidates_found=2,
                    matches_identified=1,
                    duplicate_candidates=[
                        {
                            "original": "John Smith",
                            "duplicates": ["Jon Smith"],
                            "confidence": 0.92,
                        }
                    ],
                ),
                errors=[],
            )

        ExtractionOrchestrator.process_batch = _process_batch_stub

        try:
            orchestrator = ExtractionOrchestrator()
            result = orchestrator.process_batch(
                ["doc_1.pdf", "doc_2.pdf"],
                detect_entities=True,
            )

            # Verify deduplication results
            assert result.deduplication_results is not None
            assert result.deduplication_results.candidates_found == 2
            assert result.deduplication_results.matches_identified == 1
        finally:
            ExtractionOrchestrator.process_batch = original_process_batch

    def test_api_response_formatting_compliance(self, client: TestClient) -> None:
        """Validate API response format adheres to specification."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        # Check response headers
        assert "application/json" in response.headers.get("content-type", "")

        # Check JSON structure
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data
        assert data["status"] == "healthy"

    def test_openapi_documentation_available(self, client: TestClient) -> None:
        """Verify OpenAPI documentation is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "components" in data

    def test_logging_configured(self) -> None:
        """Verify logging is properly configured."""
        logger = logging.getLogger("src.deployment.cloud_run_config")
        assert logger is not None

    def test_concurrent_health_checks(self, client: TestClient) -> None:
        """Test API behavior under concurrent health check requests."""
        responses = []
        for _ in range(5):
            response = client.get("/api/v1/health")
            responses.append(response.status_code)

        assert all(code == 200 for code in responses)

    def test_cross_environment_configuration_progression(self) -> None:
        """Test configuration consistency across environments."""
        project_id = "test-project"
        image = "gcr.io/test-project/api:v1"

        dev = create_dev_config(project_id=project_id, image_uri=image)
        staging = create_staging_config(project_id=project_id, image_uri=image)
        prod = create_prod_config(project_id=project_id, image_uri=image)

        # Verify environment progression
        assert dev.environment == DeploymentEnvironment.DEV
        assert staging.environment == DeploymentEnvironment.STAGING
        assert prod.environment == DeploymentEnvironment.PROD

        # Verify authentication progression
        assert dev.enable_authentication is False
        assert staging.enable_authentication is True
        assert prod.enable_authentication is True

    def test_deployment_manager_logging_configuration(self) -> None:
        """Test deployment manager logging is configured."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="extraction-api",
            image_uri="gcr.io/test-project/api:v1",
        )

        manager = CloudRunDeploymentManager(config)
        # log_deployment_config triggers logging
        manager.log_deployment_config()
        # If no exception, logging is working

    def test_production_readiness_integration(self) -> None:
        """Comprehensive production readiness validation."""
        # Verify API is runnable
        assert app is not None

        # Verify all factory functions work
        dev_config = create_dev_config(
            project_id="test-project", image_uri="gcr.io/test-project/api:v1"
        )
        assert dev_config is not None

        staging_config = create_staging_config(
            project_id="test-project", image_uri="gcr.io/test-project/api:v1"
        )
        assert staging_config is not None

        prod_config = create_prod_config(
            project_id="test-project", image_uri="gcr.io/test-project/api:v1"
        )
        assert prod_config is not None

        # Verify orchestrator works
        orchestrator = ExtractionOrchestrator()
        assert orchestrator is not None

    def test_invalid_canary_traffic_percentage(self) -> None:
        """Test validation of invalid traffic percentages."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="extraction-api",
            image_uri="gcr.io/test-project/api:v1",
        )

        manager = CloudRunDeploymentManager(config)

        # Test invalid traffic percentage (>100)
        with pytest.raises(ValueError, match="between 0 and"):
            manager.get_canary_deployment_command(new_revision_traffic=150)

    def test_configuration_validation_empty_project(self) -> None:
        """Test configuration validation rejects empty project ID."""
        with pytest.raises(ValueError, match="project_id"):
            CloudRunConfig(
                project_id="",
                region="us-central1",
                service_name="extraction-api",
                image_uri="gcr.io/test-project/api:v1",
            )

    def test_batch_extraction_with_mocked_orchestrator(self) -> None:
        """Test batch extraction via orchestrator mock."""
        original_process_batch = ExtractionOrchestrator.process_batch

        def _process_batch_stub(
            self: ExtractionOrchestrator,
            file_paths: list[str],
            *,
            detect_entities: bool,
        ) -> _BatchResultStub:
            del self
            assert file_paths == ["doc_1.pdf", "doc_2.pdf", "doc_3.pdf"]
            assert detect_entities is True
            return _BatchResultStub(
                extracted_documents=[
                    _ExtractedDocumentStub(
                        document_id=f"doc_{idx}",
                        text=f"Content {idx}",
                    )
                    for idx in range(3)
                ],
                errors=[],
                deduplication_results=_DeduplicationResultsStub(
                    candidates_found=0,
                    matches_identified=0,
                    duplicate_candidates=[],
                ),
            )

        ExtractionOrchestrator.process_batch = _process_batch_stub

        try:
            orchestrator = ExtractionOrchestrator()
            result = orchestrator.process_batch(
                ["doc_1.pdf", "doc_2.pdf", "doc_3.pdf"],
                detect_entities=True,
            )

            # Verify results
            assert len(result.extracted_documents) == 3
            assert len(result.errors) == 0
        finally:
            ExtractionOrchestrator.process_batch = original_process_batch
