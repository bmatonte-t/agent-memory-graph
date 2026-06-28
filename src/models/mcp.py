"""Typed contracts for Phase 3 MCP tool invocation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, cast

from pydantic import BaseModel, Field, model_validator

from src.security.governance import AuthorizationScope  # noqa: TC001


class MCPToolName(StrEnum):
    """Supported Phase 3 MCP tool names."""

    MEMORY_SEARCH = "memory_search"
    MEMORY_ADD_FACT = "memory_add_fact"
    MEMORY_LOG_TRACE = "memory_log_trace"
    MEMORY_RECALL_CONTEXT = "memory_recall_context"


class MCPInvokeRequest(BaseModel):
    """Tool invocation request payload."""

    tenant_id: str = Field(
        ...,
        description=(
            "Tenant identifier. Required in multi-tenant mode. "
            "Auto-injected in org-wide single-company mode."
        ),
    )
    agent_id: str | None = Field(default=None, min_length=1)
    tool_name: MCPToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def _inject_tenant_id_in_org_wide_mode(cls, data: object) -> object:
        """Inject the fixed company_id when org-wide mode is active and tenant_id is absent.

        In multi-tenant mode this validator is a no-op; a missing or null
        ``tenant_id`` will still fail Pydantic field validation (422).

        In single-company mode a missing or null ``tenant_id`` is replaced
        with the configured ``company_id`` before type checking occurs.
        """
        if not isinstance(data, dict):
            return data
        typed_data = cast(dict[str, Any], data)
        if typed_data.get("tenant_id") is not None:
            return typed_data

        from src.project_base.settings import settings  # noqa: PLC0415

        if settings.single_company.enabled:
            result = dict(typed_data)
            result["tenant_id"] = settings.single_company.company_id
            return result
        return typed_data

    request_id: str | None = Field(default=None)
    authorization_scope: AuthorizationScope | None = Field(default=None)


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
