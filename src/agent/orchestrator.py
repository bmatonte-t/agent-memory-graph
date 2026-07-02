"""Phase 3 agent orchestration loop built on MCP tools."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from src.models.agent import (
    AgentExecutionMode,
    AgentOrchestrationRequest,
    AgentOrchestrationResponse,
    AgentToolCallTrace,
)
from src.models.mcp import MCPInvokeRequest, MCPInvokeResponse, MCPToolName
from src.observability.logging import structured_log
from src.observability.metrics import orchestrator_request_counter
from src.observability.tracing import trace_span

if TYPE_CHECKING:
    from src.agent.vertex_adapter import VertexAgentAdapter
    from src.mcp.service import MCPToolService

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT_EXTRACTION_WINDOW = 50


@dataclass(slots=True)
class AgentOrchestrator:
    """Minimal single-agent orchestration loop for Phase 3 baseline."""

    mcp_tool_service: MCPToolService
    vertex_adapter: VertexAgentAdapter | None = None

    async def respond(self, request: AgentOrchestrationRequest) -> AgentOrchestrationResponse:
        """Run one agent turn through MCP tools.

        Args:
            request: User prompt and session context.

        Returns:
            AgentOrchestrationResponse: Final text and tool trace.
        """
        with trace_span(
            "orchestrator.respond",
            attributes={
                "tenant.id": request.tenant_id,
                "session.id": request.session_id or "",
                "request.id": request.request_id or "",
                "agent.mode": str(request.mode),
            },
        ):
            request_id = request.request_id or f"req_{uuid4()}"
            execution_mode = request.mode

            if request.mode == AgentExecutionMode.VERTEX:
                if self.vertex_adapter is None:
                    logger.warning(
                        "agent_orchestration_fallback %s",
                        json.dumps(
                            {
                                "requested_mode": request.mode,
                                "fallback_mode": AgentExecutionMode.SINGLE,
                                "reason": "vertex_adapter_not_configured",
                                "session_id": request.session_id,
                                "request_id": request.request_id,
                            },
                            default=str,
                        ),
                    )
                    execution_mode = AgentExecutionMode.SINGLE
                    orchestrator_coro = self._respond_single_mode(
                        request=request,
                        request_id=request_id,
                        execution_mode=execution_mode,
                    )
                else:
                    orchestrator_coro = self.vertex_adapter.respond(request)
            elif request.mode == AgentExecutionMode.SUPERVISOR_WORKER:
                orchestrator_coro = self._respond_supervisor_worker_mode(
                    request=request,
                    request_id=request_id,
                )
            else:
                execution_mode = AgentExecutionMode.SINGLE
                orchestrator_coro = self._respond_single_mode(
                    request=request,
                    request_id=request_id,
                    execution_mode=execution_mode,
                )

            if request.timeout_ms is None:
                return await orchestrator_coro

            timeout_seconds = request.timeout_ms / 1000
            try:
                return await asyncio.wait_for(orchestrator_coro, timeout=timeout_seconds)
            except TimeoutError:
                return await self._handle_timeout(
                    request=request,
                    request_id=request_id,
                    execution_mode=execution_mode,
                )

    async def _respond_single_mode(
        self,
        request: AgentOrchestrationRequest,
        request_id: str,
        execution_mode: AgentExecutionMode,
    ) -> AgentOrchestrationResponse:
        """Execute baseline single-agent tool flow.

        Args:
            request: User prompt and session context.
            request_id: Stable request identifier to propagate.
            execution_mode: Mode reported in response telemetry.

        Returns:
            AgentOrchestrationResponse: Final text and tool trace.
        """
        tool_calls: list[AgentToolCallTrace] = []

        structured_log(
            logger,
            logging.INFO,
            "agent_orchestration_start",
            {
                "tenant_id": request.tenant_id,
                "session_id": request.session_id,
                "request_id": request_id,
                "mode": str(execution_mode),
            },
        )

        context_response = await self._invoke_tool(
            MCPInvokeRequest(
                tenant_id=request.tenant_id,
                agent_id=request.agent_id,
                tool_name=MCPToolName.MEMORY_RECALL_CONTEXT,
                arguments={"window_size": 10},
                session_id=request.session_id,
                request_id=request_id,
                authorization_scope=request.authorization_scope,
            )
        )
        tool_calls.append(self._to_tool_trace(context_response))

        search_response = await self._invoke_tool(
            MCPInvokeRequest(
                tenant_id=request.tenant_id,
                agent_id=request.agent_id,
                tool_name=MCPToolName.MEMORY_SEARCH,
                arguments={"query": request.prompt},
                session_id=request.session_id,
                request_id=request_id,
                authorization_scope=request.authorization_scope,
            )
        )
        tool_calls.append(self._to_tool_trace(search_response))

        response_text, grounded = self._extract_synthesis(search_response)

        trace_context = {
            "request_id": request_id,
            "prompt": request.prompt,
            "context_success": context_response.success,
            "search_success": search_response.success,
            "tool_calls": [trace.model_dump(mode="json") for trace in tool_calls],
        }
        log_response = await self._invoke_tool(
            MCPInvokeRequest(
                tenant_id=request.tenant_id,
                agent_id=request.agent_id,
                tool_name=MCPToolName.MEMORY_LOG_TRACE,
                arguments={
                    "event_type": "AGENT_ORCHESTRATION_TURN",
                    "decision_context": trace_context,
                    "source_node_id": request.session_id,
                },
                session_id=request.session_id,
                request_id=request_id,
                authorization_scope=request.authorization_scope,
            )
        )
        tool_calls.append(self._to_tool_trace(log_response))

        structured_log(
            logger,
            logging.INFO,
            "agent_orchestration_finish",
            {
                "tenant_id": request.tenant_id,
                "session_id": request.session_id,
                "request_id": request_id,
                "mode": str(execution_mode),
                "grounded": grounded,
                "tool_call_count": len(tool_calls),
            },
        )

        orchestrator_request_counter().add(
            1,
            {
                "agent.mode": str(execution_mode),
                "grounded": str(grounded),
                "tenant.id": request.tenant_id,
            },
        )

        return AgentOrchestrationResponse(
            session_id=request.session_id,
            request_id=request_id,
            execution_mode=execution_mode,
            response_text=response_text,
            grounded=grounded,
            tool_call_count=len(tool_calls),
            tool_calls=tool_calls,
        )

    async def _respond_supervisor_worker_mode(
        self,
        request: AgentOrchestrationRequest,
        request_id: str,
    ) -> AgentOrchestrationResponse:
        """Execute supervisor-worker orchestration path.

        Args:
            request: User prompt and session context.
            request_id: Stable request identifier to propagate.

        Returns:
            AgentOrchestrationResponse: Final text and tool trace.
        """
        tool_calls: list[AgentToolCallTrace] = []

        structured_log(
            logger,
            logging.INFO,
            "agent_orchestration_start",
            {
                "tenant_id": request.tenant_id,
                "session_id": request.session_id,
                "request_id": request_id,
                "mode": str(AgentExecutionMode.SUPERVISOR_WORKER),
            },
        )

        context_request = MCPInvokeRequest(
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            tool_name=MCPToolName.MEMORY_RECALL_CONTEXT,
            arguments={"window_size": 20},
            session_id=request.session_id,
            request_id=request_id,
            authorization_scope=request.authorization_scope,
        )
        search_request = MCPInvokeRequest(
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            tool_name=MCPToolName.MEMORY_SEARCH,
            arguments={"query": request.prompt},
            session_id=request.session_id,
            request_id=request_id,
            authorization_scope=request.authorization_scope,
        )

        context_response, search_response = await asyncio.gather(
            self._invoke_tool(context_request),
            self._invoke_tool(search_request),
        )

        tool_calls.append(self._to_tool_trace(context_response))
        tool_calls.append(self._to_tool_trace(search_response))

        response_text, grounded = self._extract_synthesis(search_response)

        trace_context = {
            "request_id": request_id,
            "prompt": request.prompt,
            "orchestration_pattern": "supervisor_worker",
            "worker_context_success": context_response.success,
            "worker_search_success": search_response.success,
            "tool_calls": [trace.model_dump(mode="json") for trace in tool_calls],
        }
        log_response = await self._invoke_tool(
            MCPInvokeRequest(
                tenant_id=request.tenant_id,
                agent_id=request.agent_id,
                tool_name=MCPToolName.MEMORY_LOG_TRACE,
                arguments={
                    "event_type": "AGENT_ORCHESTRATION_SUPERVISOR_WORKER_TURN",
                    "decision_context": trace_context,
                    "source_node_id": request.session_id,
                },
                session_id=request.session_id,
                request_id=request_id,
                authorization_scope=request.authorization_scope,
            )
        )
        tool_calls.append(self._to_tool_trace(log_response))

        structured_log(
            logger,
            logging.INFO,
            "agent_orchestration_finish",
            {
                "tenant_id": request.tenant_id,
                "session_id": request.session_id,
                "request_id": request_id,
                "mode": str(AgentExecutionMode.SUPERVISOR_WORKER),
                "grounded": grounded,
                "tool_call_count": len(tool_calls),
            },
        )

        return AgentOrchestrationResponse(
            session_id=request.session_id,
            request_id=request_id,
            execution_mode=AgentExecutionMode.SUPERVISOR_WORKER,
            response_text=response_text,
            grounded=grounded,
            tool_call_count=len(tool_calls),
            tool_calls=tool_calls,
        )

    @staticmethod
    def _extract_synthesis(search_response: MCPInvokeResponse) -> tuple[str, bool]:
        """Extract synthesized response from search tool output.

        Args:
            search_response: Search tool response payload.

        Returns:
            tuple[str, bool]: Response text and grounded flag.
        """
        response_text = "Insufficient graph evidence."
        grounded = False

        if not search_response.success:
            return response_text, grounded

        if not isinstance(search_response.result, dict):
            return response_text, grounded

        result: dict[str, object] = search_response.result

        synthesis = result.get("synthesis")
        if not isinstance(synthesis, dict):
            return response_text, grounded

        synthesis_dict = cast(dict[str, object], synthesis)
        response_text_value = synthesis_dict.get("response_text", response_text)
        grounded_value = synthesis_dict.get("grounded", False)

        response_text = str(response_text_value)
        grounded = bool(grounded_value)
        return response_text, grounded

    async def _invoke_tool(self, request: MCPInvokeRequest) -> MCPInvokeResponse:
        """Invoke MCP tool service.

        Args:
            request: Tool invocation request.

        Returns:
            MCPInvokeResponse: Tool execution response.
        """
        return await self.mcp_tool_service.invoke(request)

    async def _handle_timeout(
        self,
        request: AgentOrchestrationRequest,
        request_id: str,
        execution_mode: AgentExecutionMode,
    ) -> AgentOrchestrationResponse:
        """Handle orchestration timeout and trigger session closure protocol.

        Args:
            request: Orchestration request that timed out.
            request_id: Stable request identifier.
            execution_mode: Mode to report in the response payload.

        Returns:
            AgentOrchestrationResponse: Timeout response enriched with closure trace.
        """
        timeout_response = await self._invoke_tool(
            MCPInvokeRequest(
                tenant_id=request.tenant_id,
                agent_id=request.agent_id,
                tool_name=MCPToolName.MEMORY_END_SESSION,
                arguments={
                    "end_reason": "timeout",
                    "window_size": DEFAULT_TIMEOUT_EXTRACTION_WINDOW,
                },
                session_id=request.session_id,
                request_id=request_id,
                authorization_scope=request.authorization_scope,
            )
        )

        structured_log(
            logger,
            logging.WARNING,
            "agent_orchestration_timeout",
            {
                "tenant_id": request.tenant_id,
                "session_id": request.session_id,
                "request_id": request_id,
                "mode": str(execution_mode),
                "timeout_ms": request.timeout_ms,
                "session_close_success": timeout_response.success,
            },
        )

        return AgentOrchestrationResponse(
            session_id=request.session_id,
            request_id=request_id,
            execution_mode=execution_mode,
            response_text=(
                "The session timed out. Session closure and knowledge extraction were triggered."
            ),
            grounded=False,
            tool_call_count=1,
            tool_calls=[self._to_tool_trace(timeout_response)],
        )

    @staticmethod
    def _to_tool_trace(response: MCPInvokeResponse) -> AgentToolCallTrace:
        """Convert MCP responses into orchestration trace items.

        Args:
            response: Tool execution response.

        Returns:
            AgentToolCallTrace: Normalized trace item.
        """
        error_code = response.error.code if response.error else None
        total_tokens = response.token_usage.total_tokens if response.token_usage else None
        return AgentToolCallTrace(
            tool_name=response.tool_name,
            request_id=response.request_id,
            success=response.success,
            latency_ms=response.latency_ms,
            total_tokens=total_tokens,
            error_code=error_code,
        )
