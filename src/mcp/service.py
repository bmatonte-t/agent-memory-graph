"""Phase 3 MCP tool service implementation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from src.memory.api import MemoryAPI
from src.memory.mindmap_pipeline import MindMapPipeline, MindMapPipelineError
from src.models.mcp import (
    MCPInvokeRequest,
    MCPInvokeResponse,
    MCPTokenUsage,
    MCPToolError,
    MCPToolName,
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

    async def invoke(self, request: MCPInvokeRequest) -> MCPInvokeResponse:
        """Invoke a supported tool and return a typed response.

        Args:
            request: Tool invocation request.

        Returns:
            MCPInvokeResponse: Typed tool invocation result.
        """
        started = perf_counter()
        logger.info(
            "mcp_tool_invoke_start %s",
            json.dumps(
                {
                    "tool_name": request.tool_name,
                    "session_id": request.session_id,
                    "request_id": request.request_id,
                },
                default=str,
            ),
        )
        try:
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

    async def _memory_search(self, request: MCPInvokeRequest) -> dict[str, Any]:
        """Invoke the MindMap query pipeline.

        Args:
            request: Tool invocation request.

        Returns:
            dict[str, Any]: Serialized MindMap response.
        """
        query = request.arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise MCPToolServiceError(
                code="validation_error",
                message="memory_search requires non-empty 'query'",
            )

        session_id = request.arguments.get("session_id") or request.session_id

        try:
            response = await self.mindmap_pipeline.execute(query=query, session_id=session_id)
        except MindMapPipelineError as error:
            raise MCPToolServiceError(
                code=str(error.code),
                message=str(error),
                retryable=False,
            ) from error

        return response.model_dump(mode="json")

    async def _memory_add_fact(self, request: MCPInvokeRequest) -> dict[str, Any]:
        """Ingest semantic memory fact via MemoryAPI.

        Args:
            request: Tool invocation request.

        Returns:
            dict[str, Any]: Serialized fact response.
        """
        entity_type = request.arguments.get("entity_type")
        entity_id = request.arguments.get("entity_id")
        attributes = request.arguments.get("attributes", {})
        relationship = request.arguments.get("relationship")

        if not isinstance(entity_type, str) or not isinstance(entity_id, str):
            raise MCPToolServiceError(
                code="validation_error",
                message="memory_add_fact requires string 'entity_type' and 'entity_id'",
            )
        if not isinstance(attributes, dict):
            raise MCPToolServiceError(
                code="validation_error",
                message="memory_add_fact 'attributes' must be an object",
            )
        if relationship is not None and not isinstance(relationship, dict):
            raise MCPToolServiceError(
                code="validation_error",
                message="memory_add_fact 'relationship' must be an object when provided",
            )

        try:
            response = await MemoryAPI.add_semantic_fact(
                entity_type=entity_type,
                entity_id=entity_id,
                attributes=attributes,
                relationship=relationship,
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

        return response.model_dump(mode="json")

    async def _memory_log_trace(self, request: MCPInvokeRequest) -> dict[str, Any]:
        """Write reasoning metadata into audit memory.

        Args:
            request: Tool invocation request.

        Returns:
            dict[str, Any]: Serialized audit response.
        """
        decision_context = request.arguments.get("decision_context")
        event_type = request.arguments.get("event_type", "AGENT_REASONING_STEP")
        source_node_id = request.arguments.get("source_node_id") or request.session_id

        if not isinstance(decision_context, dict):
            raise MCPToolServiceError(
                code="validation_error",
                message="memory_log_trace requires object 'decision_context'",
            )
        if not isinstance(event_type, str) or not event_type:
            raise MCPToolServiceError(
                code="validation_error",
                message="memory_log_trace requires non-empty string 'event_type'",
            )
        if not isinstance(source_node_id, str) or not source_node_id:
            raise MCPToolServiceError(
                code="validation_error",
                message="memory_log_trace requires 'source_node_id' or request/session id",
            )

        try:
            response = await MemoryAPI.record_audit_event(
                event_type=event_type,
                source_node_id=source_node_id,
                context=decision_context,
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

        return response.model_dump(mode="json")

    async def _memory_recall_context(self, request: MCPInvokeRequest) -> dict[str, Any]:
        """Recall recent context turns for a session.

        Args:
            request: Tool invocation request.

        Returns:
            dict[str, Any]: Serialized context response.
        """
        session_id = request.arguments.get("session_id") or request.session_id
        window_size = request.arguments.get("window_size", 10)

        if not isinstance(session_id, str) or not session_id:
            raise MCPToolServiceError(
                code="validation_error",
                message="memory_recall_context requires string 'session_id'",
            )
        if not isinstance(window_size, int):
            raise MCPToolServiceError(
                code="validation_error",
                message="memory_recall_context 'window_size' must be an integer",
            )

        try:
            response = await MemoryAPI.retrieve_context_window(
                session_id=session_id,
                window_size=window_size,
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

        return response.model_dump(mode="json")
