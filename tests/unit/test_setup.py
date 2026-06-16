"""Unit tests for project setup and initialization."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.mark.unit
class TestProjectSetup:
    """Tests for project setup and basic functionality."""

    def test_fastapi_app_creation(self):
        """Test that FastAPI app is created successfully."""
        assert app is not None
        assert app.title == "Agent Memory Graph API"

    def test_health_check_endpoint(self):
        """Test health check endpoint."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["database"] == "initialized"

    def test_spanner_client_singleton(self):
        """Test that SpannerClient is a proper singleton."""
        from src.db.spanner_client import SpannerClient

        client1 = SpannerClient()
        client2 = SpannerClient()
        assert client1 is client2

    def test_spanner_client_requires_initialization(self):
        """Test that SpannerClient raises error if used before initialization."""
        from src.db.spanner_client import SpannerClient

        # Reset the singleton
        SpannerClient._instance = None
        SpannerClient._client = None
        SpannerClient._database = None

        client = SpannerClient()
        with pytest.raises(RuntimeError, match="not initialized"):
            client.get_client()

        with pytest.raises(RuntimeError, match="not initialized"):
            client.get_database()

    def test_pydantic_models_import(self):
        """Test that Pydantic models can be imported."""
        from src.models.schemas import (
            AuditResponse,
            ContextResponse,
            FactResponse,
            SessionResponse,
        )

        # Verify all models can be instantiated
        from datetime import datetime

        session = SessionResponse(session_id="test", created_at=datetime.utcnow())
        assert session.session_id == "test"

        fact = FactResponse(
            entity_id="test",
            entity_type="PERSON",
            node_path="/test",
            created_at=datetime.utcnow(),
        )
        assert fact.entity_type == "PERSON"

        audit = AuditResponse(
            event_id="test", event_type="TEST", timestamp=datetime.utcnow()
        )
        assert audit.event_type == "TEST"

        context = ContextResponse(
            session_id="test", turns=[], retrieved_at=datetime.utcnow()
        )
        assert context.session_id == "test"
        assert len(context.turns) == 0
