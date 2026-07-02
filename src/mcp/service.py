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
    MCPDiscoveryResponse,
    MCPErrorManifest,
    MCPInvokeRequest,
    MCPInvokeResponse,
    MCPTokenUsage,
    MCPToolError,
    MCPToolManifest,
    MCPToolName,
    MCPToolParameter,
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
class AuthorizationDecision:
    """Authorization decision with explicit reason code for audit trail."""

    allowed: bool
    reason_code: str  # e.g., AUTHORIZED_AGENT_SCOPE, DENIED_NODE_ID_NOT_ALLOWED
    details: str | None = None  # Optional details for logging


@dataclass(slots=True)
class MCPToolService:
    """Service that exposes memory capabilities as MCP tools."""

    mindmap_pipeline: MindMapPipeline

    _SUPPORTED_DISCOVERY_VERSIONS = ("1.0",)

    def get_discovery_manifest(self, requested_version: str | None = None) -> MCPDiscoveryResponse:
        """Return versioned discovery manifest for MCP client auto-configuration.

        Args:
            requested_version: Optional requested contract version.

        Returns:
            MCPDiscoveryResponse: Versioned MCP discovery metadata.

        Raises:
            ValueError: If requested version is unsupported.
        """
        normalized_version = self._normalize_discovery_version(requested_version)
        tools = self._build_tool_manifest()
        errors = self._build_error_manifest()
        capabilities = [
            "tenant_isolation",
            "authorization_scope",
            "estimated_token_usage",
            "session_context_pagination",
            "session_knowledge_extraction",
            "partial_failure_batch_ingestion",
        ]

        return MCPDiscoveryResponse(
            manifest_version="1.0",
            requested_version=normalized_version,
            supported_versions=list(self._SUPPORTED_DISCOVERY_VERSIONS),
            invoke_endpoint="/api/v1/mcp/invoke",
            capabilities=capabilities,
            tools=tools,
            tool_catalog=tools,
            errors=errors,
            compatibility_notes=[
                "Additive fields are backward-compatible within major version 1.",
                "Unknown fields should be ignored by clients.",
            ],
        )

    def _normalize_discovery_version(self, requested_version: str | None) -> str:
        """Normalize requested manifest version and enforce supported set."""
        if requested_version is None:
            return "1.0"

        normalized = requested_version.strip()
        if normalized in {"", "1", "1.0"}:
            return "1.0"

        supported = ", ".join(self._SUPPORTED_DISCOVERY_VERSIONS)
        msg = f"unsupported discovery version: {requested_version}. Supported: {supported}"
        raise ValueError(msg)

    def _build_tool_manifest(self) -> list[MCPToolManifest]:
        """Build discovery metadata for all supported tools."""
        return [
            MCPToolManifest(
                name=MCPToolName.MEMORY_SEARCH,
                description="Query grounded memory through MindMap pipeline.",
                parameters=[
                    MCPToolParameter(
                        name="query",
                        type="string",
                        required=True,
                        description="Natural-language question for memory retrieval.",
                    ),
                    MCPToolParameter(
                        name="session_id",
                        type="string",
                        required=False,
                        description="Session identifier used for trace continuity.",
                        default=None,
                    ),
                ],
                error_codes=["validation_error", "permission_denied", "backend_error"],
            ),
            MCPToolManifest(
                name=MCPToolName.MEMORY_ADD_FACT,
                description="Write a semantic memory fact with optional relationship.",
                parameters=[
                    MCPToolParameter(
                        name="entity_type",
                        type="string",
                        required=True,
                        description="Node label/type for the semantic entity.",
                    ),
                    MCPToolParameter(
                        name="entity_id",
                        type="string",
                        required=True,
                        description="Stable identifier for the semantic entity.",
                    ),
                    MCPToolParameter(
                        name="attributes",
                        type="object",
                        required=False,
                        description="JSON object with entity attributes.",
                        default={},
                    ),
                    MCPToolParameter(
                        name="relationship",
                        type="object",
                        required=False,
                        description="Optional relationship payload to create an edge.",
                        default=None,
                    ),
                ],
                error_codes=["validation_error", "permission_denied", "backend_error"],
            ),
            MCPToolManifest(
                name=MCPToolName.MEMORY_ADD_FACT_BATCH,
                description="Write multiple semantic facts with partial failure reporting.",
                parameters=[
                    MCPToolParameter(
                        name="facts",
                        type="array<object>",
                        required=True,
                        description="Non-empty array of semantic fact payloads.",
                    ),
                    MCPToolParameter(
                        name="session_id",
                        type="string",
                        required=False,
                        description="Session identifier used for action counting.",
                        default=None,
                    ),
                ],
                error_codes=["validation_error", "permission_denied", "backend_error"],
            ),
            MCPToolManifest(
                name=MCPToolName.MEMORY_LOG_TRACE,
                description="Persist reasoning/audit trace events.",
                parameters=[
                    MCPToolParameter(
                        name="decision_context",
                        type="object",
                        required=True,
                        description="Structured reasoning context to persist.",
                    ),
                    MCPToolParameter(
                        name="event_type",
                        type="string",
                        required=False,
                        description="Audit event type.",
                        default="AGENT_REASONING_STEP",
                    ),
                    MCPToolParameter(
                        name="source_node_id",
                        type="string",
                        required=False,
                        description="Source node id; falls back to session_id.",
                        default=None,
                    ),
                ],
                error_codes=["validation_error", "permission_denied", "backend_error"],
            ),
            MCPToolManifest(
                name=MCPToolName.MEMORY_RECALL_CONTEXT,
                description="Retrieve session context window for grounded response generation.",
                parameters=[
                    MCPToolParameter(
                        name="session_id",
                        type="string",
                        required=True,
                        description="Session identifier to retrieve.",
                    ),
                    MCPToolParameter(
                        name="window_size",
                        type="integer",
                        required=False,
                        description="Number of turns to retrieve.",
                        default=10,
                    ),
                    MCPToolParameter(
                        name="cursor",
                        type="string",
                        required=False,
                        description="Pagination cursor for context retrieval.",
                        default=None,
                    ),
                ],
                error_codes=["validation_error", "permission_denied", "backend_error"],
            ),
            MCPToolManifest(
                name=MCPToolName.MEMORY_END_SESSION,
                description="Close session and trigger knowledge extraction.",
                parameters=[
                    MCPToolParameter(
                        name="session_id",
                        type="string",
                        required=True,
                        description="Session identifier to close.",
                    ),
                    MCPToolParameter(
                        name="end_reason",
                        type="string",
                        required=False,
                        description="Reason used for closure semantics.",
                        default="completed",
                    ),
                    MCPToolParameter(
                        name="domain_hint",
                        type="string",
                        required=False,
                        description="Optional domain hint for extraction quality.",
                        default=None,
                    ),
                    MCPToolParameter(
                        name="window_size",
                        type="integer",
                        required=False,
                        description="Context window used during extraction.",
                        default=50,
                    ),
                ],
                error_codes=["validation_error", "permission_denied", "backend_error"],
            ),
        ]

    @staticmethod
    def _build_error_manifest() -> list[MCPErrorManifest]:
        """Build stable error-code catalog for discovery clients."""
        return [
            MCPErrorManifest(
                code="validation_error",
                retryable=False,
                description="Request payload did not satisfy the MCP tool contract.",
            ),
            MCPErrorManifest(
                code="permission_denied",
                retryable=False,
                description="Authorization scope denied requested operation.",
            ),
            MCPErrorManifest(
                code="backend_error",
                retryable=True,
                description="Transient backend/storage failure during tool execution.",
            ),
        ]

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
                auth_decision = self._authorize_request(request)
                if not auth_decision.allowed:
                    error_msg = f"authorization denied: {auth_decision.reason_code}"
                    raise PermissionError(error_msg)  # noqa: TRY301

                # Audit log: authorization granted — must not be silently swallowed;
                # a write failure here indicates a security-critical storage problem.
                await MemoryAPI.record_audit_event(
                    tenant_id=request.tenant_id,
                    event_type="MCP_AUTHORIZATION_GRANTED",
                    source_node_id=request.authorization_scope.agent_id
                    if request.authorization_scope
                    else "unknown",
                    context={
                        "tool_name": str(request.tool_name),
                        "reason_code": auth_decision.reason_code,
                        "details": auth_decision.details or "",
                        "session_id": request.session_id or "",
                        "request_id": request.request_id or "",
                    },
                )

                if request.tool_name == MCPToolName.MEMORY_SEARCH:
                    result = await self._memory_search(request)
                elif request.tool_name == MCPToolName.MEMORY_ADD_FACT:
                    result = await self._memory_add_fact(request)
                elif request.tool_name == MCPToolName.MEMORY_ADD_FACT_BATCH:
                    result = await self._memory_add_fact_batch(request)
                elif request.tool_name == MCPToolName.MEMORY_LOG_TRACE:
                    result = await self._memory_log_trace(request)
                elif request.tool_name == MCPToolName.MEMORY_RECALL_CONTEXT:
                    result = await self._memory_recall_context(request)
                elif request.tool_name == MCPToolName.MEMORY_END_SESSION:
                    result = await self._memory_end_session(request)
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
                structured_log(
                    logger,
                    logging.INFO,
                    "mcp_tool_invoke_finish",
                    {
                        "tenant_id": request.tenant_id,
                        "tool_name": str(request.tool_name),
                        "request_id": request.request_id,
                        "success": response.success,
                        "latency_ms": response.latency_ms,
                        "error_code": response.error.code if response.error else "",
                        "total_tokens": response.token_usage.total_tokens
                        if response.token_usage
                        else 0,
                    },
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
                # Audit log: authorization denied
                try:
                    auth_context = request.arguments.copy() if request.arguments else {}
                    auth_context.update(
                        {
                            "tool_name": str(request.tool_name),
                            "reason_code": str(error).split(": ")[-1]
                            if ": " in str(error)
                            else "DENIED_UNKNOWN",
                        }
                    )
                    await MemoryAPI.record_audit_event(
                        tenant_id=request.tenant_id,
                        event_type="MCP_AUTHORIZATION_DENIED",
                        source_node_id=request.authorization_scope.agent_id
                        if request.authorization_scope
                        else "unknown",
                        context=auth_context,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning("Failed to audit MCP_AUTHORIZATION_DENIED: %s", e)

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
            structured_log(
                logger,
                logging.INFO,
                "mcp_tool_invoke_finish",
                {
                    "tenant_id": request.tenant_id,
                    "tool_name": str(request.tool_name),
                    "request_id": request.request_id,
                    "success": response.success,
                    "latency_ms": response.latency_ms,
                    "error_code": "",
                    "total_tokens": response.token_usage.total_tokens
                    if response.token_usage
                    else 0,
                },
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
    def _authorize_request(
        request: MCPInvokeRequest,
    ) -> AuthorizationDecision:
        """Evaluate authorization decision with explicit reason code.

        Args:
            request: Tool invocation request.

        Returns:
            AuthorizationDecision with allowed status and reason code.
        """
        from src.project_base.settings import settings  # noqa: PLC0415

        if not settings.governance.authorization.enabled:
            return AuthorizationDecision(
                allowed=True,
                reason_code="AUTHORIZATION_DISABLED",
                details="Authorization enforcement not enabled",
            )

        scope = request.authorization_scope
        if scope is None:
            return AuthorizationDecision(
                allowed=False,
                reason_code="MISSING_AUTHORIZATION_SCOPE",
                details="No authorization scope provided in request",
            )

        node_id: str | None = None
        allowed = False
        reason = "DENIED_UNKNOWN"
        details = ""

        if request.tool_name == MCPToolName.MEMORY_SEARCH:
            node_id = request.session_id or request.arguments.get("session_id")
            allowed = scope.allows_resource(
                node_id=node_id,
                label="Session",
                memory_tier="CONTEXT",
            )
            reason = "AUTHORIZED_AGENT_SCOPE" if allowed else "DENIED_SESSION_NOT_ALLOWED"
            details = f"session_id={node_id}"
        if request.tool_name == MCPToolName.MEMORY_ADD_FACT:
            entity_id = request.arguments.get("entity_id")
            entity_type = request.arguments.get("entity_type")
            relationship = request.arguments.get("relationship")  # type: ignore[arg-type]
            rel_type: str | None = None
            if isinstance(relationship, dict):
                validated_relationship = validate_relationship(cast("dict[str, Any]", relationship))
                if validated_relationship is not None:
                    rel_type = validated_relationship.get("type")
            allowed = scope.allows_resource(
                node_id=entity_id,
                label=entity_type,
                memory_tier="SEMANTIC",
                relationship_type=rel_type,
            )
            reason = "AUTHORIZED_AGENT_SCOPE" if allowed else "DENIED_NODE_ID_NOT_ALLOWED"
            details = f"entity_id={entity_id} entity_type={entity_type}"
        if request.tool_name == MCPToolName.MEMORY_ADD_FACT_BATCH:
            # Per-item authorization is delegated to MemoryAPI.add_semantic_fact so this
            # pre-check only ensures an explicit authorization scope is present.
            allowed = True
            reason = "AUTHORIZED_AGENT_SCOPE_BATCH_DEFERRED"
            details = "batch_memory_add_fact"
        if request.tool_name == MCPToolName.MEMORY_LOG_TRACE:
            node_id = request.session_id or request.arguments.get("source_node_id")
            allowed = scope.allows_resource(
                node_id=node_id,
                label="AUDIT_EVENT",
                memory_tier="AUDIT",
            )
            reason = "AUTHORIZED_AGENT_SCOPE" if allowed else "DENIED_AUDIT_ACCESS_NOT_ALLOWED"
            details = f"source_node_id={node_id}"
        if request.tool_name == MCPToolName.MEMORY_RECALL_CONTEXT:
            node_id = request.session_id or request.arguments.get("session_id")
            allowed = scope.allows_resource(
                node_id=node_id,
                label="Session",
                memory_tier="CONTEXT",
            )
            reason = "AUTHORIZED_AGENT_SCOPE" if allowed else "DENIED_SESSION_NOT_ALLOWED"
            details = f"session_id={node_id}"
        if request.tool_name == MCPToolName.MEMORY_END_SESSION:
            node_id = request.session_id or request.arguments.get("session_id")
            allowed = scope.allows_resource(
                node_id=node_id,
                label="Session",
                memory_tier="CONTEXT",
            )
            reason = "AUTHORIZED_AGENT_SCOPE" if allowed else "DENIED_SESSION_NOT_ALLOWED"
            details = f"session_id={node_id}"

        if request.tool_name not in (
            MCPToolName.MEMORY_SEARCH,
            MCPToolName.MEMORY_ADD_FACT,
            MCPToolName.MEMORY_ADD_FACT_BATCH,
            MCPToolName.MEMORY_LOG_TRACE,
            MCPToolName.MEMORY_RECALL_CONTEXT,
            MCPToolName.MEMORY_END_SESSION,
        ):
            return AuthorizationDecision(
                allowed=False,
                reason_code="DENIED_UNSUPPORTED_TOOL",
                details=f"tool_name={request.tool_name}",
            )

        return AuthorizationDecision(
            allowed=allowed,
            reason_code=reason,
            details=details,
        )

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

    async def _memory_add_fact_batch(self, request: MCPInvokeRequest) -> dict[str, Any]:
        """Ingest multiple semantic facts with per-item partial-failure reporting.

        Args:
            request: Tool invocation request.

        Returns:
            dict[str, Any]: Batch summary, successes, and failures.
        """
        tenant_id = validate_tenant_id(request.tenant_id)
        session_id = self._resolve_session_id(request)

        raw_facts = request.arguments.get("facts")
        if not isinstance(raw_facts, list) or not raw_facts:
            msg = "memory_add_fact_batch facts must be a non-empty array"
            raise MCPToolServiceError(code="validation_error", message=msg)
        facts = cast("list[object]", raw_facts)

        successes: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []

        for index, raw_item in enumerate(facts):
            entity_id: str | None = None
            try:
                fact_item = cast(
                    "dict[str, Any]",
                    validate_mapping(raw_item, field_name=f"facts[{index}]"),
                )
                entity_type = validate_required_string(
                    cast("str | None", fact_item.get("entity_type")),
                    field_name=f"facts[{index}].entity_type",
                )
                entity_id = validate_required_string(
                    cast("str | None", fact_item.get("entity_id")),
                    field_name=f"facts[{index}].entity_id",
                )
                attributes = validate_mapping(
                    fact_item.get("attributes", {}),
                    field_name=f"facts[{index}].attributes",
                )
                relationship_input = fact_item.get("relationship")
                relationship = (
                    validate_relationship(
                        cast(
                            "dict[str, Any]",
                            validate_mapping(
                                relationship_input,
                                field_name=f"facts[{index}].relationship",
                            ),
                        )
                    )
                    if relationship_input is not None
                    else None
                )

                fact_response = await MemoryAPI.add_semantic_fact(
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
                successes.append(fact_response.model_dump(mode="json"))
            except PermissionError as error:
                failures.append(
                    {
                        "index": index,
                        "entity_id": entity_id,
                        "code": "permission_denied",
                        "message": str(error),
                        "retryable": False,
                    }
                )
            except ValueError as error:
                failures.append(
                    {
                        "index": index,
                        "entity_id": entity_id,
                        "code": "validation_error",
                        "message": str(error),
                        "retryable": False,
                    }
                )
            except RuntimeError as error:
                failures.append(
                    {
                        "index": index,
                        "entity_id": entity_id,
                        "code": "backend_error",
                        "message": str(error),
                        "retryable": True,
                    }
                )

        if session_id is not None:
            MemoryAPI._increment_session_action_count(  # noqa: SLF001  # type: ignore[attr-defined]
                request.tenant_id,
                session_id,
            )

        return {
            "total_items": len(facts),
            "succeeded": len(successes),
            "failed": len(failures),
            "partial_failure": bool(failures),
            "successful_items": successes,
            "failed_items": failures,
        }

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
            cursor_argument = request.arguments.get("cursor")
            cursor = (
                validate_required_string(cursor_argument, field_name="cursor")
                if cursor_argument is not None
                else None
            )
        except ValueError as error:
            raise MCPToolServiceError(
                code="validation_error",
                message=f"memory_recall_context {error}",
            ) from error

        try:
            retrieval_arguments: dict[str, Any] = {
                "tenant_id": tenant_id,
                "session_id": session_id,
                "window_size": window_size,
                "authorization_scope": request.authorization_scope,
            }
            if cursor is not None:
                retrieval_arguments["cursor"] = cursor

            response = await MemoryAPI.retrieve_context_window(**retrieval_arguments)
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

    async def _memory_end_session(self, request: MCPInvokeRequest) -> dict[str, Any]:
        """Close a session and trigger knowledge extraction from session context.

        Args:
            request: Tool invocation request.

        Returns:
            dict[str, Any]: Serialized session closure response.
        """
        try:
            tenant_id = validate_tenant_id(request.tenant_id)
            session_id = validate_required_string(
                self._resolve_session_id(request),
                field_name="session_id",
            )
            end_reason = validate_required_string(
                request.arguments.get("end_reason", "completed"),
                field_name="end_reason",
            )
            domain_hint = validate_optional_string(
                request.arguments.get("domain_hint"),
                field_name="domain_hint",
            )
            window_size = validate_window_size(request.arguments.get("window_size", 50))
        except ValueError as error:
            raise MCPToolServiceError(
                code="validation_error",
                message=f"memory_end_session {error}",
            ) from error

        try:
            response = await MemoryAPI.end_session(
                tenant_id=tenant_id,
                session_id=session_id,
                end_reason=end_reason,
                domain_hint=domain_hint,
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

        return response.model_dump(mode="json")
