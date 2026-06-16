"""Unit tests for project setup and initialization."""

from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.db.spanner_client import SpannerClient
from src.models.schemas import AuditResponse, ContextResponse, FactResponse, SessionResponse


@pytest.mark.unit
class TestProjectSetup:
    """Tests for project setup and basic functionality."""

    def test_fastapi_app_creation(self) -> None:
        """Test that FastAPI app is created successfully."""
        assert app is not None
        assert app.title == "Agent Memory Graph API"

    def test_health_check_endpoint(self) -> None:
        """Test health check endpoint."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == HTTPStatus.OK
        assert response.json()["status"] == "healthy"
        assert response.json()["database"] == "initialized"

    def test_spanner_client_singleton(self) -> None:
        """Test that SpannerClient is a proper singleton."""
        client1 = SpannerClient()
        client2 = SpannerClient()
        assert client1 is client2

    def test_spanner_client_requires_initialization(self) -> None:
        """Test that SpannerClient raises error if used before initialization."""
        # Reset the singleton
        SpannerClient._instance = None
        SpannerClient._client = None
        SpannerClient._database = None

        client = SpannerClient()
        with pytest.raises(RuntimeError, match="not initialized"):
            client.get_client()

        with pytest.raises(RuntimeError, match="not initialized"):
            client.get_database()

    def test_pydantic_models_import(self) -> None:
        """Test that Pydantic models can be imported."""
        # Verify all models can be instantiated
        session = SessionResponse(session_id="test", created_at=datetime.now(UTC))
        assert session.session_id == "test"

        fact = FactResponse(
            entity_id="test",
            entity_type="PERSON",
            node_path="/test",
            created_at=datetime.now(UTC),
        )
        assert fact.entity_type == "PERSON"

        audit = AuditResponse(
            event_id="test", event_type="TEST", timestamp=datetime.now(UTC)
        )
        assert audit.event_type == "TEST"

        context = ContextResponse(
            session_id="test", turns=[], retrieved_at=datetime.now(UTC)
        )
        assert context.session_id == "test"
        assert len(context.turns) == 0
