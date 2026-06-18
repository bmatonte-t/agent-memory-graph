"""Typed contracts for Phase 3 MCP tool invocation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MCPToolName(StrEnum):
    """Supported Phase 3 MCP tool names."""

    MEMORY_SEARCH = "memory_search"
    MEMORY_ADD_FACT = "memory_add_fact"
    MEMORY_LOG_TRACE = "memory_log_trace"
    MEMORY_RECALL_CONTEXT = "memory_recall_context"


class MCPInvokeRequest(BaseModel):
    """Tool invocation request payload."""

    tool_name: MCPToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = Field(default=None)
    request_id: str | None = Field(default=None)


class MCPToolError(BaseModel):
    """Stable error details returned by tool invocation."""

    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    retryable: bool = Field(default=False)


class MCPTokenUsage(BaseModel):
    """Token usage telemetry for one tool invocation."""

    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)
    estimated: bool = Field(default=True)


class MCPInvokeResponse(BaseModel):
    """Tool invocation response payload."""

    tool_name: MCPToolName
    request_id: str | None = Field(default=None)
    success: bool
    latency_ms: float = Field(..., ge=0.0)
    result: dict[str, Any] | None = Field(default=None)
    error: MCPToolError | None = Field(default=None)
    token_usage: MCPTokenUsage | None = Field(default=None)
