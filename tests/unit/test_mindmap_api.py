"""Unit tests for MindMap HTTP endpoint contracts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app


class TestMindMapApi:
    """HTTP contract tests for Phase 2 execution endpoint."""

    def test_execute_endpoint_returns_traceable_response(self) -> None:
        """Execute endpoint should return synthesis and trace fields."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/mindmap/execute",
            json={"query": "Explain project alpha budget trend", "session_id": "session_1"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["query"] == "Explain project alpha budget trend"
        assert "synthesis" in payload
        assert "trace" in payload
        assert payload["trace"]["trace_id"].startswith("trace_")

    def test_execute_endpoint_rejects_empty_query(self) -> None:
        """Endpoint should map pipeline validation errors to HTTP 400."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/mindmap/execute",
            json={"query": "   ", "session_id": "session_1"},
        )

        assert response.status_code == 400
        assert "validation_error" in response.json()["detail"]
