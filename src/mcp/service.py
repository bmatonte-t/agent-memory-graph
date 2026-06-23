"""Phase 3 MCP tool service implementation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any, cast

from src.memory.api import MemoryAPI
from src.memory.mindmap_pipeline import MindMapPipeline, MindMapPipelineError
from src.models.mcp import (
    MCPInvokeRequest,
    MCPInvokeResponse,
    MCPTokenUsage,
    MCPToolError,
    MCPToolName,
)
from src.observability.logging import structured_log
from src.observability.metrics import mcp_tool_error_counter, mcp_tool_invocation_counter
from src.observability.tracing import trace_span
from src.security.validators import (
    validate_mapping,
    validate_optional_string,
    validate_relationship,  # type: ignore[import-untyped]
    validate_required_string,
    validate_tenant_id,
    validate_window_size,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MCPToolServiceError(RuntimeError):
    """Error raised for stable MCP tool contract responses."""

    code: str
    message: str
    retryable: bool = False


@dataclass(slots=True)
class MCPToolService:
    """Service that exposes memory capabilities as MCP tools."""

    mindmap_pipeline: MindMapPipeline

    def _resolve_session_id(
        self,
        request: MCPInvokeRequest,
    ) -> str | None:
        """Resolve session identifier consistently across all handlers.

        Normalizes session_id resolution to support both:
        - request.session_id (direct header)
        - request.arguments.get("session_id") (argument payload)

        Args:
            request: Tool invocation request.

        Returns:
            str | None: Resolved session identifier, or None if not provided.
        """
        return validate_optional_string(
            request.arguments.get("session_id") or request.session_id,
            field_name="session_id",
        )

    async def invoke(self, request: MCPInvokeRequest) -> MCPInvokeResponse:
        """Invoke a supported tool and return a typed response.

        Args:
            request: Tool invocation request.

        Returns:
            MCPInvokeResponse: Typed tool invocation result.
        """
        started = perf_counter()
        with trace_span(
            "mcp.invoke",
            attributes={
                "tenant.id": request.tenant_id,
                "tool.name": str(request.tool_name),
                "session.id": request.session_id or "",
                "request.id": request.request_id or "",
            },
        ):
            structured_log(
                logger,
                logging.INFO,
                "mcp_tool_invoke_start",
                {
                    "tenant_id": request.tenant_id,
                    "tool_name": str(request.tool_name),
                    "session_id": request.session_id or "",
                    "request_id": request.request_id or "",
                },
            )
            try:
                self._authorize_request(request)
                if request.tool_name == MCPToolName.MEMORY_SEARCH:
                    result = await self._memory_search(request)
                elif request.tool_name == MCPToolName.MEMORY_ADD_FACT:
                    result = await self._memory_add_fact(request)
                elif request.tool_name == MCPToolName.MEMORY_LOG_TRACE:
                    result = await self._memory_log_trace(request)
                elif request.tool_name == MCPToolName.MEMORY_RECALL_CONTEXT:
                    result = await self._memory_recall_context(request)
                else:
                    raise MCPToolServiceError(  # noqa: TRY301
                        code="validation_error",
                        message=f"unsupported tool_name: {request.tool_name}",
                    )
            except MCPToolServiceError as error:
                token_usage = self._estimate_token_usage(
                    arguments=request.arguments,
                    result=None,
                    error_message=error.message,
                )
                response = MCPInvokeResponse(
                    tool_name=request.tool_name,
                    request_id=request.request_id,
                    success=False,
                    latency_ms=(perf_counter() - started) * 1000,
                    error=MCPToolError(
                        code=error.code,
                        message=error.message,
                        retryable=error.retryable,
                    ),
                    token_usage=token_usage,
                )
                logger.info(
                    "mcp_tool_invoke_finish %s",
                    json.dumps(
                        {
                            "tool_name": request.tool_name,
                            "request_id": request.request_id,
                            "success": response.success,
                            "latency_ms": response.latency_ms,
                            "error_code": response.error.code if response.error else None,
                            "total_tokens": response.token_usage.total_tokens
                            if response.token_usage
                            else None,
                        },
                        default=str,
                    ),
                )
                mcp_tool_error_counter().add(
                    1,
                    {
                        "tool.name": str(request.tool_name),
                        "error.code": error.code,
                        "tenant.id": request.tenant_id,
                    },
                )
                return response
            except PermissionError as error:
                token_usage = self._estimate_token_usage(
                    arguments=request.arguments,
                    result=None,
                    error_message=str(error),
                )
                response = MCPInvokeResponse(
                    tool_name=request.tool_name,
                    request_id=request.request_id,
                    success=False,
                    latency_ms=(perf_counter() - started) * 1000,
                    error=MCPToolError(
                        code="permission_denied",
                        message=str(error),
                        retryable=False,
                    ),
                    token_usage=token_usage,
                )
                mcp_tool_error_counter().add(
                    1,
                    {
                        "tool.name": str(request.tool_name),
                        "error.code": "permission_denied",
                        "tenant.id": request.tenant_id,
                    },
                )
                return response

            token_usage = self._estimate_token_usage(
                arguments=request.arguments,
                result=result,
                error_message=None,
            )
            response = MCPInvokeResponse(
                tool_name=request.tool_name,
                request_id=request.request_id,
                success=True,
                latency_ms=(perf_counter() - started) * 1000,
                result=result,
                token_usage=token_usage,
            )
            logger.info(
                "mcp_tool_invoke_finish %s",
                json.dumps(
                    {
                        "tool_name": request.tool_name,
                        "request_id": request.request_id,
                        "success": response.success,
                        "latency_ms": response.latency_ms,
                        "error_code": None,
                        "total_tokens": response.token_usage.total_tokens
                        if response.token_usage
                        else None,
                    },
                    default=str,
                ),
            )
            mcp_tool_invocation_counter().add(
                1,
                {
                    "tool.name": str(request.tool_name),
                    "success": "true",
                    "tenant.id": request.tenant_id,
                },
            )
            return response

    @staticmethod
    def _estimate_token_usage(
        arguments: dict[str, Any],
        result: dict[str, Any] | None,
        error_message: str | None,
    ) -> MCPTokenUsage:
        """Estimate token usage for observability.

        Args:
            arguments: Request arguments payload.
            result: Successful tool result.
            error_message: Error message for failed requests.

        Returns:
            MCPTokenUsage: Coarse token telemetry estimate.
        """
        input_text = json.dumps(arguments, default=str)
        output_payload: dict[str, Any] = result or {}
        if error_message:
            output_payload = {"error": error_message}
        output_text = json.dumps(output_payload, default=str)

        input_tokens = len(input_text.split())
        output_tokens = len(output_text.split())
        return MCPTokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated=True,
        )

    @staticmethod
    def _authorize_request(request: MCPInvokeRequest) -> None:
        """Enforce deny-by-default authorization before tool dispatch."""
        from src.project_base.settings import settings  # noqa: PLC0415

        scope_required_message = "authorization scope is required"
        denied_request_message = "authorization denied for request"

        if not settings.governance.authorization.enabled:
            return

        scope = request.authorization_scope
        if scope is None:
            raise PermissionError(scope_required_message)

        if request.tool_name == MCPToolName.MEMORY_SEARCH:
            allowed = scope.allows_resource(
                node_id=request.session_id or request.arguments.get("session_id"),
                label="Session",
                memory_tier="CONTEXT",
            )
        elif request.tool_name == MCPToolName.MEMORY_ADD_FACT:
            relationship = request.arguments.get("relationship")  # type: ignore[arg-type]
            rel_type: str | None = None
            if isinstance(relationship, dict):
                validated_relationship = validate_relationship(cast("dict[str, Any]", relationship))
                if validated_relationship is not None:
                    rel_type = validated_relationship.get("type")
            allowed = scope.allows_resource(
                node_id=request.arguments.get("entity_id"),
                label=request.arguments.get("entity_type"),
                memory_tier="SEMANTIC",
                relationship_type=rel_type,
            )
        elif request.tool_name == MCPToolName.MEMORY_LOG_TRACE:
            allowed = scope.allows_resource(
                node_id=request.session_id or request.arguments.get("source_node_id"),
                label="AUDIT_EVENT",
                memory_tier="AUDIT",
            )
        elif request.tool_name == MCPToolName.MEMORY_RECALL_CONTEXT:
            allowed = scope.allows_resource(
                node_id=request.session_id or request.arguments.get("session_id"),
                label="Session",
                memory_tier="CONTEXT",
            )
        else:
            allowed = False

        if not allowed:
            raise PermissionError(denied_request_message)

    async def _memory_search(self, request: MCPInvokeRequest) -> dict[str, Any]:
        """Invoke the MindMap query pipeline.

        Args:
            request: Tool invocation request.

        Returns:
            dict[str, Any]: Serialized MindMap response.
        """
        try:
            tenant_id = validate_tenant_id(request.tenant_id)
            query = validate_required_string(request.arguments.get("query"), field_name="query")
            session_id = self._resolve_session_id(request)
        except ValueError as error:
            raise MCPToolServiceError(
                code="validation_error",
                message=f"memory_search {error}",
            ) from error

        try:
            # Invoke MindMap pipeline with tenant isolation and authorization scope
            response = await self.mindmap_pipeline.execute(
                query=query,
                session_id=session_id,
                tenant_id=tenant_id,
                authorization_scope=request.authorization_scope,
            )
        except MindMapPipelineError as error:
            raise MCPToolServiceError(
                code=str(error.code),
                message=str(error),
                retryable=False,
            ) from error

        # Increment action count using resolved session_id
        if session_id is not None:
            MemoryAPI._increment_session_action_count(  # noqa: SLF001  # type: ignore[attr-defined]
                request.tenant_id,
                session_id,
            )

        return response.model_dump(mode="json")

    async def _memory_add_fact(self, request: MCPInvokeRequest) -> dict[str, Any]:
        """Ingest semantic memory fact via MemoryAPI.

        Args:
            request: Tool invocation request.

        Returns:
            dict[str, Any]: Serialized fact response.
        """
        try:
            tenant_id = validate_tenant_id(request.tenant_id)
            entity_type = validate_required_string(
                request.arguments.get("entity_type"),
                field_name="entity_type",
            )
            entity_id = validate_required_string(
                request.arguments.get("entity_id"),
                field_name="entity_id",
            )
            attributes = validate_mapping(
                request.arguments.get("attributes", {}),
                field_name="attributes",
            )
            relationship = validate_relationship(request.arguments.get("relationship"))
            session_id = self._resolve_session_id(request)
        except ValueError as error:
            raise MCPToolServiceError(
                code="validation_error",
                message=f"memory_add_fact {error}",
            ) from error

        try:
            response = await MemoryAPI.add_semantic_fact(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                attributes=attributes,
                relationship=relationship,
                session_id=session_id,
                authorization_scope=request.authorization_scope,
                source_agent_id=request.agent_id if hasattr(request, "agent_id") else None,
                source_query_id=request.request_id or None,
            )
        except ValueError as error:
            raise MCPToolServiceError(
                code="validation_error",
                message=str(error),
            ) from error
        except RuntimeError as error:
            raise MCPToolServiceError(
                code="backend_error",
                message=str(error),
                retryable=True,
            ) from error

        # Increment action count using resolved session_id
        if session_id is not None:
            MemoryAPI._increment_session_action_count(  # noqa: SLF001  # type: ignore[attr-defined]
                request.tenant_id,
                session_id,
            )

        return response.model_dump(mode="json")

    async def _memory_log_trace(self, request: MCPInvokeRequest) -> dict[str, Any]:
        """Write reasoning metadata into audit memory.

        Args:
            request: Tool invocation request.

        Returns:
            dict[str, Any]: Serialized audit response.
        """
        try:
            tenant_id = validate_tenant_id(request.tenant_id)
            decision_context = validate_mapping(
                request.arguments.get("decision_context"),
                field_name="decision_context",
            )
            event_type = validate_required_string(
                request.arguments.get("event_type", "AGENT_REASONING_STEP"),
                field_name="event_type",
            )
            source_node_id = validate_required_string(
                request.arguments.get("source_node_id") or request.session_id,
                field_name="source_node_id",
            )
            session_id = self._resolve_session_id(request)
        except ValueError as error:
            raise MCPToolServiceError(
                code="validation_error",
                message=f"memory_log_trace {error}",
            ) from error

        try:
            response = await MemoryAPI.record_audit_event(
                tenant_id=tenant_id,
                event_type=event_type,
                source_node_id=source_node_id,
                context=decision_context,
                authorization_scope=request.authorization_scope,
            )
        except ValueError as error:
            raise MCPToolServiceError(
                code="validation_error",
                message=str(error),
            ) from error
        except RuntimeError as error:
            raise MCPToolServiceError(
                code="backend_error",
                message=str(error),
                retryable=True,
            ) from error

        # Increment action count using resolved session_id if available
        if session_id is not None:
            MemoryAPI._increment_session_action_count(  # noqa: SLF001  # type: ignore[attr-defined]
                request.tenant_id,
                session_id,
            )

        return response.model_dump(mode="json")

    async def _memory_recall_context(self, request: MCPInvokeRequest) -> dict[str, Any]:
        """Recall recent context turns for a session.

        Args:
            request: Tool invocation request.

        Returns:
            dict[str, Any]: Serialized context response.
        """
        try:
            tenant_id = validate_tenant_id(request.tenant_id)
            session_id = validate_required_string(
                self._resolve_session_id(request),
                field_name="session_id",
            )
            window_size = validate_window_size(request.arguments.get("window_size", 10))
        except ValueError as error:
            raise MCPToolServiceError(
                code="validation_error",
                message=f"memory_recall_context {error}",
            ) from error

        try:
            response = await MemoryAPI.retrieve_context_window(
                tenant_id=tenant_id,
                session_id=session_id,
                window_size=window_size,
                authorization_scope=request.authorization_scope,
            )
        except ValueError as error:
            raise MCPToolServiceError(
                code="validation_error",
                message=str(error),
            ) from error
        except RuntimeError as error:
            raise MCPToolServiceError(
                code="backend_error",
                message=str(error),
                retryable=True,
            ) from error

        # Increment action count using resolved session_id
        MemoryAPI._increment_session_action_count(  # noqa: SLF001  # type: ignore[attr-defined]
            request.tenant_id,
            session_id,
        )

        return response.model_dump(mode="json")

        return response.model_dump(mode="json")
