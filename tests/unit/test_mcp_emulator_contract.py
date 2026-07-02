"""Contract tests for MCP invoke path under emulator-like runtime settings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from src.api.main import app
from src.models.schemas import AuditResponse

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

HTTP_OK = 200


class TestMcpEmulatorContract:
    """Contract coverage for deterministic MCP invoke round-trip behavior."""

    def test_memory_search_round_trip_with_stubs(
        self,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """MCP invocation should complete with deterministic test doubles."""

        class PipelineResponseStub:
            """Deterministic MindMap response stub for contract validation."""

            def model_dump(self, mode: str) -> dict[str, object]:
                """Return deterministic synthesis payload."""
                del mode
                return {
                    "query": "test",
                    "synthesis": {"response_text": "Grounded answer", "grounded": True},
                }

        async def fake_execute(**_: object) -> PipelineResponseStub:
            """Return deterministic pipeline response without external dependencies."""
            return PipelineResponseStub()

        async def fake_record_audit_event(**_: object) -> AuditResponse:
            """Return deterministic audit response for contract assertions."""
            return AuditResponse(
                tenant_id="tenant_emulator",
                event_id="audit_e2e",
                event_type="MCP_AUTHORIZATION_GRANTED",
                timestamp=datetime.now(UTC),
            )

        monkeypatch.setattr("src.api.main.mindmap_pipeline.execute", fake_execute)
        monkeypatch.setattr("src.mcp.service.MemoryAPI.record_audit_event", fake_record_audit_event)
        monkeypatch.setattr(
            "src.mcp.service.MemoryAPI._increment_session_action_count",
            lambda *_: 1,
        )

        client = TestClient(app)
        response = client.post(
            "/api/v1/mcp/invoke",
            json={
                "tenant_id": "tenant_emulator",
                "tool_name": "memory_search",
                "arguments": {"query": "hello world"},
                "session_id": "session_emulator",
                "request_id": "req_emulator_1",
            },
        )

        assert response.status_code == HTTP_OK
        payload = response.json()
        assert payload["success"] is True
        assert payload["result"]["synthesis"]["grounded"] is True
        assert payload["result"]["synthesis"]["response_text"] == "Grounded answer"
