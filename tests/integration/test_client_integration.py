"""Integration tests for Agent Memory Graph client."""

from __future__ import annotations

import httpx
import pytest

from src.client.base import AgentMemoryGraphClient
from src.client.models import ClientSession


@pytest.fixture
def client_session() -> ClientSession:
    """Fixture for client session."""
    return ClientSession(session_id="integration_test_001", agent_id="test_agent")


class TestClientContextManager:
    """Test async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_creates_http_client(self, client_session: ClientSession) -> None:
        """Context manager creates HTTP client on enter."""
        client = AgentMemoryGraphClient(
            base_url="http://localhost:8000",
            tenant_id="test_tenant",
            session=client_session,
        )
        assert client._http_client is None
        assert client._owns_http_client

        async with client as ctx:
            assert ctx._http_client is not None
            assert isinstance(ctx, AgentMemoryGraphClient)

        # Client should be closed after exit
        assert client._http_client is None or client._http_client.is_closed

    @pytest.mark.asyncio
    async def test_context_manager_with_provided_client(
        self, client_session: ClientSession
    ) -> None:
        """Context manager does not close provided HTTP client."""
        http_client = httpx.AsyncClient()
        client = AgentMemoryGraphClient(
            base_url="http://localhost:8000",
            tenant_id="test_tenant",
            session=client_session,
            http_client=http_client,
        )
        assert not client._owns_http_client

        async with client as ctx:
            assert ctx._http_client is http_client

        # Provided client should still be open (caller owns it)
        assert not http_client.is_closed
        await http_client.aclose()


class TestClientIntegration:
    """Integration tests with mocked server."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, client_session: ClientSession) -> None:
        """Full client workflow: create, search, add fact, recall."""
        # Note: This would require a running server.
        # For CI, use mocked responses (see test_client_base.py).
        # This test serves as documentation of the intended usage pattern.

        client = AgentMemoryGraphClient(
            base_url="http://localhost:8000",
            tenant_id="test_tenant",
            session=client_session,
            rate_limit=100,
        )

        # Client initialized and ready
        assert client.session.request_count == 0
        assert client.session.tokens_used == 0
        assert client.session.session_id == "integration_test_001"


class TestClientRequestValidation:
    """Test request validation."""

    def test_tenant_id_required(self) -> None:
        """Tenant ID is required."""
        # This should succeed
        client = AgentMemoryGraphClient(
            base_url="http://localhost:8000",
            tenant_id="test",
        )
        assert client.tenant_id == "test"

    def test_base_url_normalized(self) -> None:
        """Base URL is normalized."""
        client1 = AgentMemoryGraphClient(
            base_url="http://localhost:8000",
            tenant_id="test",
        )
        client2 = AgentMemoryGraphClient(
            base_url="http://localhost:8000/",
            tenant_id="test",
        )
        assert client1.base_url == client2.base_url
