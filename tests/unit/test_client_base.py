"""Unit tests for client base module."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.client.base import AgentMemoryGraphClient
from src.client.models import ClientSession
from src.client.retry import RetryConfig
from src.models.mcp import MCPInvokeResponse, MCPToolError, MCPTokenUsage


@pytest.fixture
def client_session() -> ClientSession:
    """Fixture for test session."""
    return ClientSession(session_id="test_session_001", agent_id="test_agent")


@pytest.fixture
def client(client_session: ClientSession) -> AgentMemoryGraphClient:
    """Fixture for test client."""
    client = AgentMemoryGraphClient(
        base_url="http://localhost:8000",
        tenant_id="test_tenant",
        session=client_session,
        rate_limit=1000,  # No rate limiting in tests
    )
    client._http_client = AsyncMock(spec=httpx.AsyncClient)
    return client


class TestClientInitialization:
    """Test client initialization."""

    def test_client_init_default_session(self) -> None:
        """Client auto-creates session if omitted."""
        client = AgentMemoryGraphClient(
            base_url="http://localhost:8000",
            tenant_id="test_tenant",
        )
        assert client.session.session_id.startswith("session_")
        assert client.tenant_id == "test_tenant"

    def test_client_init_custom_session(self, client_session: ClientSession) -> None:
        """Client accepts custom session."""
        client = AgentMemoryGraphClient(
            base_url="http://localhost:8000",
            tenant_id="test_tenant",
            session=client_session,
        )
        assert client.session.session_id == client_session.session_id
        assert client.session.agent_id == client_session.agent_id

    def test_client_base_url_trailing_slash_stripped(self) -> None:
        """Client strips trailing slashes from base_url."""
        client = AgentMemoryGraphClient(
            base_url="http://localhost:8000/",
            tenant_id="test_tenant",
        )
        assert client.base_url == "http://localhost:8000"


class TestMemorySearch:
    """Test memory_search tool."""

    @pytest.mark.asyncio
    async def test_search_success(self, client: AgentMemoryGraphClient) -> None:
        """Successful memory search."""
        # Mock response
        response_data = {
            "tool_name": "memory_search",
            "success": True,
            "latency_ms": 123.45,
            "result": {
                "results": [
                    {
                        "entity_id": "flight_001",
                        "weight": 0.75,
                    }
                ],
                "total_retrieved": 1,
            },
            "token_usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
            },
        }
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.json.return_value = response_data
        client.http_client.post = AsyncMock(return_value=mock_response)

        # Execute
        result = await client.search(query="flights to New York", limit=5)

        # Verify
        assert result["total_retrieved"] == 1
        assert len(result["results"]) == 1
        assert client.session.request_count == 1
        assert client.session.tokens_used == 30

    @pytest.mark.asyncio
    async def test_search_limits_parameters(
        self, client: AgentMemoryGraphClient
    ) -> None:
        """Search enforces parameter limits."""
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.json.return_value = {
            "tool_name": "memory_search",
            "success": True,
            "latency_ms": 1.0,
            "result": {},
        }
        client.http_client.post = AsyncMock(return_value=mock_response)

        # Execute with out-of-range params
        await client.search(query="test", limit=500, cognitive_weight_threshold=2.0)

        # Verify limits applied
        call_args = client.http_client.post.call_args
        request_body = call_args.kwargs["json"]
        assert request_body["arguments"]["limit"] == 100  # capped
        assert request_body["arguments"]["cognitive_weight_threshold"] == 1.0  # capped


class TestMemoryAddFact:
    """Test memory_add_fact tool."""

    @pytest.mark.asyncio
    async def test_add_fact_success(self, client: AgentMemoryGraphClient) -> None:
        """Successful fact addition."""
        response_data = {
            "tool_name": "memory_add_fact",
            "success": True,
            "latency_ms": 50.0,
            "result": {
                "entity_id": "person_alice_001",
                "weight": 0.5,
                "source_confidence_score": 1.0,
                "created_at": "2026-06-27T15:30:00Z",
            },
            "token_usage": {"input_tokens": 5, "output_tokens": 10, "total_tokens": 15},
        }
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.json.return_value = response_data
        client.http_client.post = AsyncMock(return_value=mock_response)

        # Execute
        result = await client.add_fact(
            entity_type="PERSON",
            entity_id="person_alice_001",
            attributes={"name": "Alice", "role": "Manager"},
            relationship={"type": "WORKS_FOR", "source_id": "org_1"},
        )

        # Verify
        assert result["entity_id"] == "person_alice_001"
        assert result["weight"] == 0.5

    @pytest.mark.asyncio
    async def test_add_fact_without_relationship(
        self, client: AgentMemoryGraphClient
    ) -> None:
        """Add fact without relationship."""
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.json.return_value = {
            "tool_name": "memory_add_fact",
            "success": True,
            "latency_ms": 1.0,
            "result": {"entity_id": "test"},
        }
        client.http_client.post = AsyncMock(return_value=mock_response)

        await client.add_fact(
            entity_type="PERSON",
            entity_id="test",
            attributes={"name": "Test"},
        )

        call_args = client.http_client.post.call_args
        request_body = call_args.kwargs["json"]
        assert "relationship" not in request_body["arguments"]


class TestMemoryLogTrace:
    """Test memory_log_trace tool."""

    @pytest.mark.asyncio
    async def test_log_trace_success(self, client: AgentMemoryGraphClient) -> None:
        """Successful trace logging."""
        response_data = {
            "tool_name": "memory_log_trace",
            "success": True,
            "latency_ms": 10.0,
            "result": {
                "event_id": "trace_abc123",
                "timestamp": "2026-06-27T15:30:00Z",
                "audit_logged": True,
            },
        }
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.json.return_value = response_data
        client.http_client.post = AsyncMock(return_value=mock_response)

        # Execute
        result = await client.log_trace(
            source_node_id="reasoner_agent",
            action="search_initiated",
            context={"query": "test", "latency_ms": 100},
        )

        # Verify
        assert result["event_id"] == "trace_abc123"
        assert result["audit_logged"]


class TestMemoryRecallContext:
    """Test memory_recall_context tool."""

    @pytest.mark.asyncio
    async def test_recall_context_success(
        self, client: AgentMemoryGraphClient
    ) -> None:
        """Successful context recall."""
        response_data = {
            "tool_name": "memory_recall_context",
            "success": True,
            "latency_ms": 25.0,
            "result": {
                "session_id": "test_session_001",
                "turns": [
                    {"turn_id": "turn_1", "role": "user", "weight": 0.9}
                ],
                "total_weight_sum": 0.9,
            },
        }
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.json.return_value = response_data
        client.http_client.post = AsyncMock(return_value=mock_response)

        # Execute
        result = await client.recall_context(window_size=5)

        # Verify
        assert result["session_id"] == "test_session_001"
        assert len(result["turns"]) == 1


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_tool_failure_raises_value_error(
        self, client: AgentMemoryGraphClient
    ) -> None:
        """Tool failure response raises ValueError."""
        response_data = {
            "tool_name": "memory_search",
            "success": False,
            "latency_ms": 5.0,
            "error": {
                "code": "validation_error",
                "message": "query is required",
                "retryable": False,
            },
        }
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.json.return_value = response_data
        client.http_client.post = AsyncMock(return_value=mock_response)

        # Execute & verify
        with pytest.raises(ValueError, match="query is required"):
            await client.search(query="")

    @pytest.mark.asyncio
    async def test_http_error_propagates(
        self, client: AgentMemoryGraphClient
    ) -> None:
        """HTTP errors propagate after retries exhausted."""
        client.http_client.post = AsyncMock(
            side_effect=httpx.HTTPError("Connection refused")
        )

        # HTTPError retries, so we expect RuntimeError after exhaustion
        with pytest.raises(RuntimeError, match="All 3 retry attempts exhausted"):
            await client.search(query="test")


class TestSessionTracking:
    """Test session tracking."""

    def test_session_increments_request_count(self, client_session: ClientSession) -> None:
        """Session tracks request count and token usage."""
        assert client_session.request_count == 0
        client_session.increment_request(token_count=100)
        assert client_session.request_count == 1
        assert client_session.tokens_used == 100
        client_session.increment_request(token_count=50)
        assert client_session.request_count == 2
        assert client_session.tokens_used == 150

    def test_session_to_dict(self, client_session: ClientSession) -> None:
        """Session exports metadata as dict."""
        client_session.increment_request(token_count=50)
        metadata = client_session.to_dict()
        assert metadata["session_id"] == client_session.session_id
        assert metadata["request_count"] == 1
        assert metadata["tokens_used"] == 50
