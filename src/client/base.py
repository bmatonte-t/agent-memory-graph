"""Core Agent Memory Graph client for MCP tool invocation."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Self

import httpx

from src.client.models import ClientSession
from src.client.rate_limit import RateLimiter
from src.client.retry import RetryConfig, async_retry_with_backoff
from src.models.mcp import MCPInvokeRequest, MCPInvokeResponse, MCPToolName

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)


class AgentMemoryGraphClient:
    """Typed async client for agent-memory-graph MCP tools.

    Provides methods for:
    - Memory search and retrieval
    - Fact addition and updates
    - Trace logging for audit
    - Session context recall

    Features:
    - Automatic session management
    - Rate limiting (100 req/min default)
    - Exponential backoff retry (503, 504, timeout)
    - Full Pydantic type safety
    - Async-first design with sync wrapper available
    """

    def __init__(
        self,
        base_url: str,
        tenant_id: str,
        session: ClientSession | None = None,
        http_client: httpx.AsyncClient | None = None,
        rate_limit: int = 100,
        retry_config: RetryConfig | None = None,
        timeout_sec: float = 30.0,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Server base URL (e.g., "https://agent-memory-graph.run.app")
            tenant_id: Tenant identifier for org-wide mode.
            session: Optional ClientSession; auto-created if omitted.
            http_client: Optional httpx.AsyncClient; created if omitted.
            rate_limit: Requests per minute (default 100).
            retry_config: Optional retry configuration.
            timeout_sec: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.tenant_id = tenant_id
        self.session = session or ClientSession()
        self._http_client = http_client
        self._owns_http_client = http_client is None
        self.rate_limiter = RateLimiter(rate_limit=rate_limit, window_sec=60)
        self.retry_config = retry_config or RetryConfig()
        self.timeout_sec = timeout_sec

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        if self._owns_http_client:
            self._http_client = httpx.AsyncClient()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        del exc_type, exc_val, exc_tb
        if self._owns_http_client and self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            msg = "HTTP client not initialized. Use async context manager."
            raise RuntimeError(msg)
        return self._http_client

    async def search(
        self,
        query: str,
        limit: int = 10,
        cognitive_weight_threshold: float = 0.3,
        max_age_days: int | None = None,
    ) -> dict[str, Any]:
        """Search the semantic graph for related memories.

        Args:
            query: Natural-language search string.
            limit: Max results (1-100, default 10).
            cognitive_weight_threshold: Minimum weight filter (0.0-1.0).
            max_age_days: Filter out facts older than N days.

        Returns:
            Dict with results, total_retrieved, cognitive_horizon_applied.

        Raises:
            httpx.HTTPError: On network or HTTP errors.
            ValueError: On validation errors.
        """
        arguments: dict[str, Any] = {
            "query": query,
            "limit": min(100, max(1, limit)),
            "cognitive_weight_threshold": max(0.0, min(1.0, cognitive_weight_threshold)),
        }
        if max_age_days is not None:
            arguments["max_age_days"] = max(1, max_age_days)

        return await self._invoke_tool(
            MCPToolName.MEMORY_SEARCH,
            arguments,
        )

    async def add_fact(
        self,
        entity_type: str,
        entity_id: str,
        attributes: dict[str, Any],
        relationship: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Add or update a semantic fact in the graph.

        Args:
            entity_type: One of PERSON, OBJECT, LOCATION, EVENT, ORGANIZATION.
            entity_id: Unique entity identifier.
            attributes: Arbitrary JSON attributes (name, email, role, etc.).
            relationship: Optional {type, source_id} link to existing entity.

        Returns:
            Dict with entity_id, node_path, weight, source_confidence_score, created_at.

        Raises:
            httpx.HTTPError: On network or HTTP errors.
            ValueError: On validation errors.
        """
        arguments: dict[str, Any] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "attributes": attributes,
        }
        if relationship:
            arguments["relationship"] = relationship

        return await self._invoke_tool(
            MCPToolName.MEMORY_ADD_FACT,
            arguments,
        )

    async def add_facts_batch(
        self,
        facts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Add multiple semantic facts in a single MCP request.

        Args:
            facts: Array of fact objects. Each item must include
                ``entity_type`` and ``entity_id`` and may include
                ``attributes`` and ``relationship``.

        Returns:
            dict[str, Any]: Batch summary with per-item success/failure data.

        Raises:
            ValueError: If `facts` is empty.
            httpx.HTTPError: On network or HTTP errors.
        """
        if not facts:
            msg = "facts must be a non-empty list"
            raise ValueError(msg)

        return await self._invoke_tool(
            MCPToolName.MEMORY_ADD_FACT_BATCH,
            {"facts": facts},
        )

    async def log_trace(
        self,
        source_node_id: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record an operational trace event (audit log).

        Args:
            source_node_id: ID of agent or service generating the event.
            action: Event type (e.g., "query_memory", "tool_invoked").
            context: Arbitrary JSON context (latency, query, etc.).

        Returns:
            Dict with event_id, timestamp, audit_logged.

        Raises:
            httpx.HTTPError: On network or HTTP errors.
            ValueError: On validation errors.
        """
        arguments: dict[str, Any] = {
            "source_node_id": source_node_id,
            "action": action,
        }
        if context:
            arguments["context"] = context

        return await self._invoke_tool(
            MCPToolName.MEMORY_LOG_TRACE,
            arguments,
        )

    async def recall_context(self, window_size: int = 10) -> dict[str, Any]:
        """Retrieve session context (recent turns, weights).

        Args:
            window_size: Number of recent turns to retrieve (1-50).

        Returns:
            Dict with session_id, turns, total_weight_sum, retrieved_at.

        Raises:
            httpx.HTTPError: On network or HTTP errors.
            ValueError: On validation errors.
        """
        arguments: dict[str, Any] = {
            "window_size": max(1, min(50, window_size)),
        }

        return await self._invoke_tool(
            MCPToolName.MEMORY_RECALL_CONTEXT,
            arguments,
        )

    async def _invoke_tool(
        self,
        tool_name: MCPToolName,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Internal method to invoke a tool with retry and rate limiting.

        Args:
            tool_name: Name of the tool.
            arguments: Tool-specific arguments.

        Returns:
            Result dict from response.result.

        Raises:
            httpx.HTTPError: On network errors.
            RuntimeError: If request fails after retries.
            ValueError: If response validation fails.
        """
        # Rate limit
        await asyncio.sleep(self.rate_limiter.wait_if_needed())

        # Build request
        request = MCPInvokeRequest(
            tenant_id=self.tenant_id,
            tool_name=tool_name,
            arguments=arguments,
            session_id=self.session.session_id,
            agent_id=self.session.agent_id,
        )

        # Invoke with retry
        async def _call() -> MCPInvokeResponse:
            url = f"{self.base_url}/api/v1/mcp/invoke"
            response = await self.http_client.post(
                url,
                json=request.model_dump(),
                timeout=self.timeout_sec,
            )
            response.raise_for_status()
            data = response.json()
            return MCPInvokeResponse(**data)

        try:
            mcp_response = await async_retry_with_backoff(
                _call,
                config=self.retry_config,
                on_retry=lambda attempt, exc: logger.warning(
                    "Retry %d for %s: %s", attempt, tool_name, type(exc).__name__
                ),
            )
        except RuntimeError:
            logger.exception("Tool invocation failed after retries")
            raise

        # Update session metrics
        self.session.increment_request(
            mcp_response.token_usage.total_tokens if mcp_response.token_usage else 0
        )

        # Validate response
        if not mcp_response.success:
            error_msg = mcp_response.error.message if mcp_response.error else "unknown error"
            logger.error(
                "Tool %s failed: %s (code: %s)",
                tool_name,
                error_msg,
                mcp_response.error.code if mcp_response.error else "N/A",
            )
            msg = f"Tool '{tool_name}' failed: {error_msg}"
            raise ValueError(msg)

        # Log latency
        logger.debug("Tool %s completed in %.1fms", tool_name, mcp_response.latency_ms)

        return mcp_response.result or {}
