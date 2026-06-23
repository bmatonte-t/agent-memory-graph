"""Unit tests for MindMap HTTP endpoint contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.schemas import AuditResponse

HTTP_OK = 200
HTTP_BAD_REQUEST = 400


class TestMindMapApi:
    """HTTP contract tests for Phase 2 execution endpoint."""

    @pytest.fixture(autouse=True)
    def _stub_audit_trace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub audit persistence for endpoint tests."""

        async def fake_record_audit_event(**_: object) -> AuditResponse:
            return AuditResponse(
                tenant_id="tenant_test",
                event_id="audit_test",
                event_type="MINDMAP_EXECUTION",
                timestamp=datetime.now(UTC),
            )

        monkeypatch.setattr(
            "src.memory.mindmap_pipeline.MemoryAPI.record_audit_event",
            fake_record_audit_event,
        )

    def test_execute_endpoint_returns_traceable_response(self) -> None:
        """Execute endpoint should return synthesis and trace fields."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/mindmap/execute",
            json={"query": "Explain project alpha budget trend", "session_id": "session_1"},
        )

        assert response.status_code == HTTP_OK
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

        assert response.status_code == HTTP_BAD_REQUEST
        assert "validation_error" in response.json()["detail"]
