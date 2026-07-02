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
    MEMORY_ADD_FACT_BATCH = "memory_add_fact_batch"
    MEMORY_LOG_TRACE = "memory_log_trace"
    MEMORY_RECALL_CONTEXT = "memory_recall_context"
    MEMORY_END_SESSION = "memory_end_session"


class MCPToolParameter(BaseModel):
    """Parameter metadata exposed by MCP discovery manifest."""

    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    required: bool
    description: str = Field(..., min_length=1)
    default: Any | None = Field(default=None)


class MCPToolManifest(BaseModel):
    """Discovery metadata for one MCP tool."""

    name: MCPToolName
    description: str = Field(..., min_length=1)
    parameters: list[MCPToolParameter] = Field(default_factory=list)
    error_codes: list[str] = Field(default_factory=list)


class MCPErrorManifest(BaseModel):
    """Stable error descriptor published by discovery endpoint."""

    code: str = Field(..., min_length=1)
    retryable: bool
    description: str = Field(..., min_length=1)


class MCPDiscoveryResponse(BaseModel):
    """Versioned discovery manifest for MCP clients."""

    manifest_version: str = Field(..., min_length=1)
    requested_version: str = Field(..., min_length=1)
    supported_versions: list[str] = Field(default_factory=list)
    invoke_endpoint: str = Field(..., min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    tools: list[MCPToolManifest] = Field(default_factory=list)
    # Compatibility alias for clients that adopted an earlier draft field name.
    tool_catalog: list[MCPToolManifest] = Field(default_factory=list)
    errors: list[MCPErrorManifest] = Field(default_factory=list)
    compatibility_notes: list[str] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "manifest_version": "1.0",
                    "requested_version": "1.0",
                    "supported_versions": ["1.0"],
                    "invoke_endpoint": "/api/v1/mcp/invoke",
                    "capabilities": [
                        "tenant_isolation",
                        "authorization_scope",
                        "estimated_token_usage",
                    ],
                    "tools": [
                        {
                            "name": "memory_search",
                            "description": "Query grounded memory through MindMap pipeline.",
                            "parameters": [
                                {
                                    "name": "query",
                                    "type": "string",
                                    "required": True,
                                    "description": "Natural language query.",
                                    "default": None,
                                }
                            ],
                            "error_codes": ["validation_error", "backend_error"],
                        }
                    ],
                    "tool_catalog": [
                        {
                            "name": "memory_search",
                            "description": "Query grounded memory through MindMap pipeline.",
                            "parameters": [
                                {
                                    "name": "query",
                                    "type": "string",
                                    "required": True,
                                    "description": "Natural language query.",
                                    "default": None,
                                }
                            ],
                            "error_codes": ["validation_error", "backend_error"],
                        }
                    ],
                    "errors": [
                        {
                            "code": "validation_error",
                            "retryable": False,
                            "description": "Request payload did not match tool contract.",
                        }
                    ],
                    "compatibility_notes": [
                        "Additive fields are backward-compatible within major version 1.",
                    ],
                }
            ]
        }
    }


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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tenant_id": "tenant_a",
                    "tool_name": "memory_add_fact",
                    "arguments": {
                        "entity_type": "PERSON",
                        "entity_id": "person_123",
                        "attributes": {"name": "Alice"},
                    },
                    "session_id": "session_1",
                    "request_id": "req_single_fact",
                },
                {
                    "tenant_id": "tenant_a",
                    "tool_name": "memory_add_fact_batch",
                    "arguments": {
                        "facts": [
                            {
                                "entity_type": "PERSON",
                                "entity_id": "person_123",
                                "attributes": {"name": "Alice"},
                            },
                            {
                                "entity_type": "ORGANIZATION",
                                "entity_id": "org_001",
                                "attributes": {"name": "LATAM"},
                            },
                        ]
                    },
                    "session_id": "session_1",
                    "request_id": "req_batch_fact",
                },
            ]
        }
    }


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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tool_name": "memory_add_fact",
                    "request_id": "req_single_fact",
                    "success": True,
                    "latency_ms": 18.2,
                    "result": {
                        "entity_id": "person_123",
                        "entity_type": "PERSON",
                        "tenant_id": "tenant_a",
                        "node_path": "/PERSON/person_123",
                    },
                },
                {
                    "tool_name": "memory_add_fact_batch",
                    "request_id": "req_batch_fact",
                    "success": True,
                    "latency_ms": 42.1,
                    "result": {
                        "total_items": 2,
                        "succeeded": 1,
                        "failed": 1,
                        "partial_failure": True,
                    },
                },
            ]
        }
    }
