"""Unit tests for env-driven Vertex adapter configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.agent.vertex_adapter import (
    LocalStubVertexAdapter,
    NotConfiguredVertexAdapter,
    build_vertex_adapter_from_env,
)
from src.models.agent import AgentExecutionMode, AgentOrchestrationRequest

if TYPE_CHECKING:
    import pytest


class TestVertexAdapterConfig:
    """Behavior tests for adapter factory and stub response."""

    def test_factory_returns_none_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Factory should disable Vertex when flag is not enabled."""
        monkeypatch.delenv("AGENT_VERTEX_ENABLED", raising=False)
        monkeypatch.delenv("AGENT_VERTEX_STUB_ENABLED", raising=False)

        adapter = build_vertex_adapter_from_env()

        assert adapter is None

    def test_factory_returns_local_stub_when_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Factory should return local stub when both flags are enabled."""
        monkeypatch.setenv("AGENT_VERTEX_ENABLED", "true")
        monkeypatch.setenv("AGENT_VERTEX_STUB_ENABLED", "true")
        monkeypatch.setenv("AGENT_VERTEX_STUB_RESPONSE", "Stub response")
        monkeypatch.setenv("AGENT_VERTEX_STUB_GROUNDED", "false")

        adapter = build_vertex_adapter_from_env()

        assert isinstance(adapter, LocalStubVertexAdapter)
        assert adapter.response_text == "Stub response"
        assert adapter.grounded is False

    def test_factory_returns_not_configured_without_stub(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Factory should return not-configured adapter when stub flag is disabled."""
        monkeypatch.setenv("AGENT_VERTEX_ENABLED", "true")
        monkeypatch.setenv("AGENT_VERTEX_STUB_ENABLED", "false")

        adapter = build_vertex_adapter_from_env()

        assert isinstance(adapter, NotConfiguredVertexAdapter)

    async def test_local_stub_responds_with_vertex_mode(self) -> None:
        """Stub adapter response should always report Vertex execution mode."""
        request = AgentOrchestrationRequest(prompt="hello", session_id="s1")
        adapter = LocalStubVertexAdapter(response_text="ok", grounded=True)

        response = await adapter.respond(request)

        assert response.execution_mode == AgentExecutionMode.VERTEX
        assert response.response_text == "ok"
        assert response.grounded is True
