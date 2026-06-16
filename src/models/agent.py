"""Typed contracts for Phase 3 agent orchestration."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from src.models.mcp import MCPToolName


class AgentExecutionMode(StrEnum):
    """Execution mode for one orchestration turn."""

    SINGLE = "single"
    SUPERVISOR_WORKER = "supervisor_worker"
    VERTEX = "vertex"


class AgentOrchestrationRequest(BaseModel):
    """Agent orchestration request payload."""

    prompt: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    request_id: str | None = Field(default=None)
    mode: AgentExecutionMode = Field(default=AgentExecutionMode.SINGLE)


class AgentToolCallTrace(BaseModel):
    """Single tool invocation trace within one orchestration turn."""

    tool_name: MCPToolName
    request_id: str | None = Field(default=None)
    success: bool
    latency_ms: float = Field(..., ge=0.0)
    total_tokens: int | None = Field(default=None, ge=0)
    error_code: str | None = Field(default=None)


class AgentOrchestrationResponse(BaseModel):
    """Agent orchestration response payload."""

    session_id: str
    request_id: str
    execution_mode: AgentExecutionMode
    response_text: str = Field(..., min_length=1)
    grounded: bool
    tool_calls: list[AgentToolCallTrace] = Field(default_factory=list)
