"""Vertex adapter seam for Phase 3 agent integration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from src.models.agent import (
    AgentExecutionMode,
    AgentOrchestrationRequest,
    AgentOrchestrationResponse,
)


class VertexAgentAdapter(Protocol):
    """Protocol for Vertex-backed orchestration execution."""

    async def respond(self, request: AgentOrchestrationRequest) -> AgentOrchestrationResponse:
        """Execute one turn through Vertex runtime.

        Args:
            request: Orchestration request payload.

        Returns:
            AgentOrchestrationResponse: Orchestrated agent response.
        """


@dataclass(slots=True)
class NotConfiguredVertexAdapter:
    """Fallback adapter used when Vertex runtime is not configured."""

    async def respond(self, request: AgentOrchestrationRequest) -> AgentOrchestrationResponse:
        """Raise explicit runtime error for missing Vertex configuration.

        Args:
            request: Orchestration request payload.

        Raises:
            RuntimeError: Always raised because adapter is a placeholder.
        """
        raise RuntimeError(
            "Vertex adapter is not configured for this environment. "
            "Use execution mode 'single' or provide a concrete VertexAgentAdapter."
        )


@dataclass(slots=True)
class LocalStubVertexAdapter:
    """Local stub adapter used for offline Vertex-mode development."""

    response_text: str = "Local stub Vertex response."
    grounded: bool = True

    async def respond(self, request: AgentOrchestrationRequest) -> AgentOrchestrationResponse:
        """Return deterministic response for local testing.

        Args:
            request: Orchestration request payload.

        Returns:
            AgentOrchestrationResponse: Stubbed orchestration response.
        """
        return AgentOrchestrationResponse(
            session_id=request.session_id,
            request_id=request.request_id or "req_vertex_stub",
            execution_mode=AgentExecutionMode.VERTEX,
            response_text=self.response_text,
            grounded=self.grounded,
            tool_calls=[],
        )


def build_vertex_adapter_from_env() -> VertexAgentAdapter | None:
    """Build Vertex adapter from environment flags.

    Returns:
        VertexAgentAdapter | None: Configured adapter when enabled, else None.
    """

    def is_enabled(name: str) -> bool:
        return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}

    if not is_enabled("AGENT_VERTEX_ENABLED"):
        return None

    if is_enabled("AGENT_VERTEX_STUB_ENABLED"):
        response_text = os.getenv("AGENT_VERTEX_STUB_RESPONSE", "Local stub Vertex response.")
        grounded = os.getenv("AGENT_VERTEX_STUB_GROUNDED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return LocalStubVertexAdapter(response_text=response_text, grounded=grounded)

    return NotConfiguredVertexAdapter()
