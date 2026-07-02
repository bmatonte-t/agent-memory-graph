"""Unit tests for Phase 3 agent orchestration API endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from src.api.main import app
from src.models.agent import (
    AgentExecutionMode,
    AgentOrchestrationRequest,
    AgentOrchestrationResponse,
    AgentToolCallTrace,
)
from src.models.schemas import (
    EndSessionResponse,
    GraphExportNode,
    GraphExportResponse,
    SessionKnowledgeExtractionResponse,
)

if TYPE_CHECKING:
    import pytest

HTTP_OK = 200
HTTP_UNPROCESSABLE_ENTITY = 422
HTTP_BAD_REQUEST = 400
HTTP_ACCEPTED = 202
HTTP_FORBIDDEN = 403


class TestAgentApi:
    """HTTP contract tests for agent orchestration endpoint."""

    def test_agent_respond_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Endpoint should return orchestrated response payload."""

        async def fake_respond(
            _self: object, request: AgentOrchestrationRequest
        ) -> AgentOrchestrationResponse:
            return AgentOrchestrationResponse(
                session_id=request.session_id,
                request_id=request.request_id or "req_123",
                execution_mode=AgentExecutionMode.SINGLE,
                response_text="Grounded answer",
                grounded=True,
                tool_calls=[
                    AgentToolCallTrace(
                        tool_name="memory_search",
                        success=True,
                        latency_ms=1.0,
                        error_code=None,
                    )
                ],
            )

        monkeypatch.setattr("src.agent.orchestrator.AgentOrchestrator.respond", fake_respond)

        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/respond",
            json={
                "tenant_id": "tenant_a",
                "prompt": "hello",
                "session_id": "sess_1",
                "request_id": "req_1",
            },
        )

        assert response.status_code == HTTP_OK
        payload = response.json()
        assert payload["session_id"] == "sess_1"
        assert payload["request_id"] == "req_1"
        assert payload["execution_mode"] == "single"
        assert payload["grounded"] is True

    def test_agent_respond_rejects_empty_prompt(self) -> None:
        """Endpoint validation should reject empty prompts."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/respond",
            json={"tenant_id": "tenant_a", "prompt": "", "session_id": "sess_1"},
        )

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_end_session_endpoint_returns_closure_summary(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Session end endpoint should return closure and extraction summary."""

        async def fake_end_session(**_: object) -> EndSessionResponse:
            return EndSessionResponse(
                tenant_id="tenant_a",
                session_id="sess_1",
                status="closed",
                end_reason="completed",
                ended_at=datetime.now(UTC),
                extraction_status="completed",
                extraction=SessionKnowledgeExtractionResponse(
                    tenant_id="tenant_a",
                    session_id="sess_1",
                    domain="general",
                    processed_turns=2,
                    extracted_facts=1,
                    skipped_facts=1,
                    failed_facts=0,
                    extracted_at=datetime.now(UTC),
                ),
            )

        monkeypatch.setattr("src.api.main.MemoryAPI.end_session", fake_end_session)

        client = TestClient(app)
        response = client.post(
            "/api/v1/session/end",
            json={
                "tenant_id": "tenant_a",
                "session_id": "sess_1",
                "end_reason": "completed",
                "window_size": 25,
            },
        )

        assert response.status_code == HTTP_OK
        payload = response.json()
        assert payload["status"] == "closed"
        assert payload["extraction_status"] == "completed"
        assert payload["extraction"]["extracted_facts"] == 1

    def test_end_session_endpoint_rejects_invalid_end_reason(self) -> None:
        """Session end endpoint should reject unsupported end reasons."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/session/end",
            json={
                "tenant_id": "tenant_a",
                "session_id": "sess_1",
                "end_reason": "invalid_reason",
            },
        )

        assert response.status_code == HTTP_BAD_REQUEST

    def test_internal_bigquery_ingest_endpoint_returns_accepted(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Internal BigQuery ingestion endpoint should accept async ingestion jobs."""

        async def fake_execute(_job_id: str, _request: object) -> None:
            return None

        monkeypatch.setattr("src.api.main._execute_bigquery_ingestion_job", fake_execute)

        client = TestClient(app)
        response = client.post(
            "/internal/ingest/bigquery",
            json={
                "project_id": "analytics-project",
                "dataset_id": "dataset_a",
                "table_id": "table_a",
                "tenant_id": "tenant_a",
            },
        )

        assert response.status_code == HTTP_ACCEPTED
        payload = response.json()
        assert payload["status"] == "accepted"
        assert payload["tenant_id"] == "tenant_a"
        assert payload["project_id"] == "analytics-project"
        assert payload["dataset_id"] == "dataset_a"
        assert payload["table_id"] == "table_a"
        assert payload["job_id"]

    def test_graph_export_endpoint_returns_json_ld_snapshot(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Graph export endpoint should return JSON-LD payload for tenant snapshots."""

        async def fake_export_graph_snapshot(**_: object) -> GraphExportResponse:
            return GraphExportResponse(
                context={"@vocab": "https://agent-memory-graph.local/vocab#"},
                graph=[
                    GraphExportNode(
                        id="node:session_1",
                        type="Session",
                        tenant_id="tenant_a",
                        memory_tier="CONTEXT",
                        label="Session",
                        weight=0.5,
                        attributes={"session_status": "active"},
                    )
                ],
                tenant_id="tenant_a",
                node_count=1,
                edge_count=0,
                exported_at=datetime.now(UTC),
            )

        monkeypatch.setattr(
            "src.api.main.MemoryAPI.export_graph_snapshot",
            fake_export_graph_snapshot,
        )

        client = TestClient(app)
        response = client.get("/api/v1/graph/export", params={"tenant_id": "tenant_a", "limit": 10})

        assert response.status_code == HTTP_OK
        payload = response.json()
        assert payload["tenant_id"] == "tenant_a"
        assert payload["node_count"] == 1
        assert payload["edge_count"] == 0
        assert len(payload["@graph"]) == 1

    def test_graph_export_endpoint_rejects_invalid_limit(self) -> None:
        """Graph export endpoint should validate limit query parameter bounds."""
        client = TestClient(app)
        response = client.get("/api/v1/graph/export", params={"tenant_id": "tenant_a", "limit": 0})

        assert response.status_code == HTTP_UNPROCESSABLE_ENTITY

    def test_graph_export_endpoint_maps_permission_errors_to_forbidden(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Graph export endpoint should map authorization denials to 403 responses."""

        async def fake_export_graph_snapshot(**_: object) -> GraphExportResponse:
            msg = "authorization denied for export_graph_snapshot"
            raise PermissionError(msg)

        monkeypatch.setattr(
            "src.api.main.MemoryAPI.export_graph_snapshot",
            fake_export_graph_snapshot,
        )

        client = TestClient(app)
        response = client.get("/api/v1/graph/export", params={"tenant_id": "tenant_a", "limit": 10})

        assert response.status_code == HTTP_FORBIDDEN
