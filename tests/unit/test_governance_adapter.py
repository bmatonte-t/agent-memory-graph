"""Unit tests for governance adapter protocol and implementations.

Tests ``GovernanceAdapter`` protocol, ``AuthorizationDecision`` dataclass,
``InternalAbacAdapter``, ``ExternalPassthroughAdapter``, and the factory
function ``build_governance_adapter()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from src.models.mcp import MCPInvokeRequest, MCPToolName

if TYPE_CHECKING:
    import pytest
from src.security.governance_adapter import (
    _ADAPTER_CACHE,
    AuthorizationDecision,
    ExternalPassthroughAdapter,
    InternalAbacAdapter,
    build_governance_adapter,
)

if TYPE_CHECKING:
    from src.project_base.settings.config import SingleCompanySettings


class TestAuthorizationDecision:
    """Tests for AuthorizationDecision dataclass."""

    def test_decision_with_all_fields(self) -> None:
        """AuthorizationDecision should capture all fields."""
        decision = AuthorizationDecision(
            allowed=True,
            reason_code="AUTHORIZED_AGENT_SCOPE",
            details="agent_id=agent_1",
        )

        assert decision.allowed is True
        assert decision.reason_code == "AUTHORIZED_AGENT_SCOPE"
        assert decision.details == "agent_id=agent_1"

    def test_decision_with_none_details(self) -> None:
        """AuthorizationDecision should allow None details."""
        decision = AuthorizationDecision(
            allowed=False,
            reason_code="DENIED_SESSION_NOT_ALLOWED",
            details=None,
        )

        assert decision.allowed is False
        assert decision.reason_code == "DENIED_SESSION_NOT_ALLOWED"
        assert decision.details is None

    def test_decision_defaults_to_none_details(self) -> None:
        """AuthorizationDecision should default details to None."""
        decision = AuthorizationDecision(
            allowed=False,
            reason_code="DENIED_UNKNOWN",
        )

        assert decision.details is None


class TestInternalAbacAdapter:
    """Tests for InternalAbacAdapter."""

    def test_adapter_creation(self) -> None:
        """InternalAbacAdapter should be instantiable."""
        adapter = InternalAbacAdapter()
        assert adapter is not None

    def test_authorization_disabled_allows_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When authorization is disabled, all requests should be allowed."""
        from src.project_base.settings import settings  # noqa: PLC0415

        monkeypatch.setattr(settings.governance.authorization, "enabled", False)
        adapter = InternalAbacAdapter()
        request = MagicMock(spec=MCPInvokeRequest)

        decision = adapter.authorize(request)

        assert decision.allowed is True
        assert decision.reason_code == "AUTHORIZATION_DISABLED"

    def test_missing_scope_denies_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Request without authorization_scope should be denied."""
        from src.project_base.settings import settings  # noqa: PLC0415

        monkeypatch.setattr(settings.governance.authorization, "enabled", True)
        adapter = InternalAbacAdapter()

        request = MagicMock(spec=MCPInvokeRequest)
        request.authorization_scope = None

        decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "MISSING_AUTHORIZATION_SCOPE"

    def test_unsupported_tool_denies_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Request with unsupported tool should be denied."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.security.governance import AuthorizationScope  # noqa: PLC0415

        monkeypatch.setattr(settings.governance.authorization, "enabled", True)
        adapter = InternalAbacAdapter()

        request = MagicMock(spec=MCPInvokeRequest)
        request.authorization_scope = AuthorizationScope(agent_id="agent_1")
        request.tool_name = "UNSUPPORTED_TOOL"

        decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "DENIED_UNSUPPORTED_TOOL"

    def test_memory_search_allowed_when_scoped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MEMORY_SEARCH should be allowed when session is in scope."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.security.governance import AuthorizationScope  # noqa: PLC0415

        monkeypatch.setattr(settings.governance.authorization, "enabled", True)
        adapter = InternalAbacAdapter()

        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["session_1"],
        )
        request = MagicMock(spec=MCPInvokeRequest)
        request.authorization_scope = scope
        request.tool_name = MCPToolName.MEMORY_SEARCH
        request.session_id = "session_1"
        request.arguments = {}

        decision = adapter.authorize(request)

        assert decision.allowed is True
        assert decision.reason_code == "AUTHORIZED_AGENT_SCOPE"

    def test_memory_search_denied_when_not_scoped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MEMORY_SEARCH should be denied when session is not in scope."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.security.governance import AuthorizationScope  # noqa: PLC0415

        monkeypatch.setattr(settings.governance.authorization, "enabled", True)
        adapter = InternalAbacAdapter()

        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["session_2"],
        )
        request = MagicMock(spec=MCPInvokeRequest)
        request.authorization_scope = scope
        request.tool_name = MCPToolName.MEMORY_SEARCH
        request.session_id = "session_1"
        request.arguments = {}

        decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "DENIED_SESSION_NOT_ALLOWED"

    def test_memory_add_fact_allowed_when_entity_scoped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MEMORY_ADD_FACT should be allowed when entity is in scope."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.security.governance import AuthorizationScope  # noqa: PLC0415

        monkeypatch.setattr(settings.governance.authorization, "enabled", True)
        adapter = InternalAbacAdapter()

        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1"],
        )
        request = MagicMock(spec=MCPInvokeRequest)
        request.authorization_scope = scope
        request.tool_name = MCPToolName.MEMORY_ADD_FACT
        request.arguments = {
            "entity_id": "entity_1",
            "entity_type": "PERSON",
            "relationship": None,
        }

        decision = adapter.authorize(request)

        assert decision.allowed is True
        assert decision.reason_code == "AUTHORIZED_AGENT_SCOPE"

    def test_memory_log_trace_allowed_when_source_scoped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MEMORY_LOG_TRACE should be allowed when source node is in scope."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.security.governance import AuthorizationScope  # noqa: PLC0415

        monkeypatch.setattr(settings.governance.authorization, "enabled", True)
        adapter = InternalAbacAdapter()

        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["source_1"],
        )
        request = MagicMock(spec=MCPInvokeRequest)
        request.authorization_scope = scope
        request.tool_name = MCPToolName.MEMORY_LOG_TRACE
        request.session_id = None
        request.arguments = {"source_node_id": "source_1"}

        decision = adapter.authorize(request)

        assert decision.allowed is True
        assert decision.reason_code == "AUTHORIZED_AGENT_SCOPE"

    def test_memory_recall_context_allowed_when_session_scoped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MEMORY_RECALL_CONTEXT should be allowed when session is in scope."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.security.governance import AuthorizationScope  # noqa: PLC0415

        monkeypatch.setattr(settings.governance.authorization, "enabled", True)
        adapter = InternalAbacAdapter()

        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["session_1"],
        )
        request = MagicMock(spec=MCPInvokeRequest)
        request.authorization_scope = scope
        request.tool_name = MCPToolName.MEMORY_RECALL_CONTEXT
        request.session_id = "session_1"
        request.arguments = {}

        decision = adapter.authorize(request)

        assert decision.allowed is True
        assert decision.reason_code == "AUTHORIZED_AGENT_SCOPE"


# Constant for external adapter timeout validation
EXTERNAL_ADAPTER_TIMEOUT_SECONDS = 10.0


class TestExternalPassthroughAdapter:
    """Tests for ExternalPassthroughAdapter."""

    def test_adapter_creation(self) -> None:
        """ExternalPassthroughAdapter should be instantiable with URL."""
        adapter = ExternalPassthroughAdapter(external_auth_url="http://localhost:8001/authorize")
        assert adapter.external_auth_url == "http://localhost:8001/authorize"

    def test_adapter_custom_timeout(self) -> None:
        """ExternalPassthroughAdapter should accept custom timeout."""
        adapter = ExternalPassthroughAdapter(
            external_auth_url="http://localhost:8001/authorize",
            _request_timeout_seconds=EXTERNAL_ADAPTER_TIMEOUT_SECONDS,
        )
        assert adapter._request_timeout_seconds == EXTERNAL_ADAPTER_TIMEOUT_SECONDS

    def test_external_auth_success(self) -> None:
        """ExternalPassthroughAdapter should delegate to external service."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = '{"tool_name": "memory_search"}'

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "allowed": True,
            "reason_code": "EXTERNAL_AUTHORIZED",
            "details": "Policy service approved",
        }

        with patch("httpx.post", return_value=mock_response):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://localhost:8001/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is True
        assert decision.reason_code == "EXTERNAL_AUTHORIZED"
        assert decision.details == "Policy service approved"

    def test_external_auth_denial(self) -> None:
        """ExternalPassthroughAdapter should respect denial from external service."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = '{"tool_name": "memory_search"}'

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "allowed": False,
            "reason_code": "EXTERNAL_DENIED",
            "details": "Policy service rejected",
        }

        with patch("httpx.post", return_value=mock_response):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://localhost:8001/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "EXTERNAL_DENIED"

    def test_external_auth_http_error(self) -> None:
        """ExternalPassthroughAdapter should deny on HTTP errors."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = '{"tool_name": "memory_search"}'

        with patch(
            "httpx.post",
            side_effect=Exception("HTTP 500 error"),
        ):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://localhost:8001/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "EXTERNAL_AUTH_UNAVAILABLE"

    def test_external_auth_timeout(self) -> None:
        """ExternalPassthroughAdapter should deny on timeout."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = '{"tool_name": "memory_search"}'

        with patch(
            "httpx.post",
            side_effect=TimeoutError("Request timed out"),
        ):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://localhost:8001/authorize",
                _request_timeout_seconds=1.0,
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "EXTERNAL_AUTH_UNAVAILABLE"

    def test_external_auth_malformed_response(self) -> None:
        """ExternalPassthroughAdapter should handle malformed JSON response."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = '{"tool_name": "memory_search"}'

        mock_response = MagicMock()
        mock_response.json.side_effect = Exception("Malformed JSON")

        with patch("httpx.post", return_value=mock_response):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://localhost:8001/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "EXTERNAL_AUTH_UNAVAILABLE"

    def test_external_auth_missing_allowed_field(self) -> None:
        """ExternalPassthroughAdapter should default allowed to False if missing."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = '{"tool_name": "memory_search"}'

        mock_response = MagicMock()
        mock_response.json.return_value = {"reason_code": "EXTERNAL_DECISION"}

        with patch("httpx.post", return_value=mock_response):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://localhost:8001/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "EXTERNAL_DECISION"


class TestBuildGovernanceAdapter:
    """Tests for build_governance_adapter factory function."""

    def teardown_method(self) -> None:
        """Clear adapter cache after each test."""
        _ADAPTER_CACHE.clear()

    def test_factory_returns_internal_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Factory should return InternalAbacAdapter when single_company disabled."""
        from src.project_base.settings import settings  # noqa: PLC0415

        monkeypatch.setattr(settings.single_company, "enabled", False)

        adapter = build_governance_adapter()

        assert isinstance(adapter, InternalAbacAdapter)

    def test_factory_returns_internal_when_internal_mode(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """Factory should return InternalAbacAdapter when auth_mode='internal'."""
        adapter = build_governance_adapter()

        assert isinstance(adapter, InternalAbacAdapter)

    def test_factory_returns_external_when_external_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Factory should return ExternalPassthroughAdapter when auth_mode='external'."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415

        org_settings = SingleCompanySettings(
            enabled=True,
            company_id="test-org",
            auth_mode="external",
            external_auth_url="http://localhost:8001/authorize",
        )
        monkeypatch.setattr(settings, "single_company", org_settings)

        adapter = build_governance_adapter()

        assert isinstance(adapter, ExternalPassthroughAdapter)

    def test_factory_caches_adapter_instance(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """Factory should cache adapter so second call returns same instance."""
        adapter1 = build_governance_adapter()
        adapter2 = build_governance_adapter()

        assert adapter1 is adapter2

    def test_factory_cache_key_differs_by_auth_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Factory should use different cache keys for internal vs external mode."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415

        # First get internal adapter
        internal_settings = SingleCompanySettings(
            enabled=True,
            company_id="test-org",
            auth_mode="internal",
        )
        monkeypatch.setattr(settings, "single_company", internal_settings)
        internal_adapter = build_governance_adapter()

        # Switch to external
        _ADAPTER_CACHE.clear()
        external_settings = SingleCompanySettings(
            enabled=True,
            company_id="test-org",
            auth_mode="external",
            external_auth_url="http://localhost:8001/authorize",
        )
        monkeypatch.setattr(settings, "single_company", external_settings)
        external_adapter = build_governance_adapter()

        assert not isinstance(internal_adapter, type(external_adapter))
        assert isinstance(internal_adapter, InternalAbacAdapter)
        assert isinstance(external_adapter, ExternalPassthroughAdapter)
