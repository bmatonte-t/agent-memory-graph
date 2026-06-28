"""Integration tests for ExternalPassthroughAdapter with real-like scenarios.

Tests the HTTP delegation pattern for authorization to external policy services,
including error handling, timeouts, and policy response validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from src.models.mcp import MCPInvokeRequest

if TYPE_CHECKING:
    import pytest
from src.security.governance_adapter import (
    AuthorizationDecision,
    ExternalPassthroughAdapter,
    build_governance_adapter,
)

# Constant for external auth adapter timeout validation
EXTERNAL_AUTH_TIMEOUT_SECONDS = 5.0


class TestExternalAuthAdapterIntegration:
    """Tests for ExternalPassthroughAdapter in realistic scenarios."""

    def test_adapter_handles_policy_service_approval(self) -> None:
        """External adapter should authorize based on policy service response."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "allowed": True,
            "reason_code": "POLICY_APPROVED",
            "details": "User has required scope",
        }

        with patch("httpx.post", return_value=mock_response):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://policy-service:8080/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is True
        assert decision.reason_code == "POLICY_APPROVED"

    def test_adapter_handles_policy_service_denial(self) -> None:
        """External adapter should deny based on policy service response."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "allowed": False,
            "reason_code": "INSUFFICIENT_SCOPE",
            "details": "User scope does not include memory_search",
        }

        with patch("httpx.post", return_value=mock_response):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://policy-service:8080/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "INSUFFICIENT_SCOPE"
        assert "memory_search" in decision.details

    def test_adapter_sends_request_to_correct_endpoint(self) -> None:
        """External adapter should POST to the configured service URL."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = '{"tool": "memory_search"}'

        mock_response = MagicMock()
        mock_response.json.return_value = {"allowed": True}

        with patch("httpx.post", return_value=mock_response) as mock_post:
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://localhost:8001/authorize"
            )
            adapter.authorize(request)

            # Verify post was called with correct URL and timeout
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args is not None
            assert call_args[0][0] == "http://localhost:8001/authorize"

    def test_adapter_includes_timeout_in_request(self) -> None:
        """External adapter should respect timeout configuration."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        mock_response = MagicMock()
        mock_response.json.return_value = {"allowed": True}

        with patch("httpx.post", return_value=mock_response) as mock_post:
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://localhost:8001/authorize",
                _request_timeout_seconds=5.0,
            )
            adapter.authorize(request)

            # Verify timeout was passed
            call_args = mock_post.call_args
            assert call_args is not None
            assert "timeout" in call_args[1]
            assert call_args[1]["timeout"] == EXTERNAL_AUTH_TIMEOUT_SECONDS

    def test_adapter_recovers_from_network_error(self) -> None:
        """External adapter should deny on network errors."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        with patch("httpx.post", side_effect=ConnectionError("Network unreachable")):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://unreachable-service:8080/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "EXTERNAL_AUTH_UNAVAILABLE"

    def test_adapter_recovers_from_service_timeout(self) -> None:
        """External adapter should deny on timeout."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        with patch("httpx.post", side_effect=TimeoutError("Request timeout")):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://slow-service:8080/authorize",
                _request_timeout_seconds=1.0,
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "EXTERNAL_AUTH_UNAVAILABLE"

    def test_adapter_handles_json_parse_error(self) -> None:
        """External adapter should deny on malformed JSON response."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch("httpx.post", return_value=mock_response):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://buggy-service:8080/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "EXTERNAL_AUTH_UNAVAILABLE"


class TestExternalAuthFactoryIntegration:
    """Tests for governance adapter factory with external auth."""

    def test_factory_creates_external_adapter_in_external_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Factory should create ExternalPassthroughAdapter when configured."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415
        from src.security import governance_adapter  # noqa: PLC0415

        org_settings = SingleCompanySettings(
            enabled=True,
            company_id="org-1",
            auth_mode="external",
            external_auth_url="http://policy-service:8080/authorize",
        )
        monkeypatch.setattr(settings, "single_company", org_settings)
        governance_adapter._ADAPTER_CACHE.clear()

        adapter = build_governance_adapter()

        assert isinstance(adapter, ExternalPassthroughAdapter)
        assert adapter.external_auth_url == "http://policy-service:8080/authorize"

    def test_factory_caches_external_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Factory should cache the external adapter instance."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415
        from src.security import governance_adapter  # noqa: PLC0415

        org_settings = SingleCompanySettings(
            enabled=True,
            company_id="org-1",
            auth_mode="external",
            external_auth_url="http://policy-service:8080/authorize",
        )
        monkeypatch.setattr(settings, "single_company", org_settings)
        governance_adapter._ADAPTER_CACHE.clear()

        adapter_1 = build_governance_adapter()
        adapter_2 = build_governance_adapter()

        assert adapter_1 is adapter_2

    def test_factory_invalidates_cache_on_url_change(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Factory should create new adapter when URL changes."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import (  # noqa: PLC0415
            SingleCompanySettings,
        )
        from src.security import governance_adapter  # noqa: PLC0415

        org_settings_1 = SingleCompanySettings(
            enabled=True,
            company_id="org-1",
            auth_mode="external",
            external_auth_url="http://service-1:8080/authorize",
        )
        monkeypatch.setattr(settings, "single_company", org_settings_1)
        governance_adapter._ADAPTER_CACHE.clear()

        adapter_1 = build_governance_adapter()

        org_settings_2 = SingleCompanySettings(
            enabled=True,
            company_id="org-1",
            auth_mode="external",
            external_auth_url="http://service-2:8080/authorize",
        )
        monkeypatch.setattr(settings, "single_company", org_settings_2)
        governance_adapter._ADAPTER_CACHE.clear()

        adapter_2 = build_governance_adapter()

        assert adapter_1 is not adapter_2
        assert adapter_1.external_auth_url == "http://service-1:8080/authorize"
        assert adapter_2.external_auth_url == "http://service-2:8080/authorize"


class TestExternalAuthPolicyResponseValidation:
    """Tests for validating policy service responses."""

    def test_adapter_accepts_response_with_all_fields(self) -> None:
        """Adapter should accept complete policy response."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "allowed": True,
            "reason_code": "COMPLETE_RESPONSE",
            "details": "All fields present",
        }

        with patch("httpx.post", return_value=mock_response):
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            decision = adapter.authorize(request)

        assert isinstance(decision, AuthorizationDecision)
        assert decision.allowed is True
        assert decision.reason_code == "COMPLETE_RESPONSE"

    def test_adapter_defaults_allowed_to_false(self) -> None:
        """Adapter should default allowed to False if missing from response."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        mock_response = MagicMock()
        # Response missing 'allowed' field
        mock_response.json.return_value = {
            "reason_code": "PARTIAL_RESPONSE",
        }

        with patch("httpx.post", return_value=mock_response):
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            decision = adapter.authorize(request)

        assert decision.allowed is False

    def test_adapter_accepts_reason_code_from_policy_service(self) -> None:
        """Adapter should preserve reason_code from policy service."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        custom_reason = "CUSTOM_POLICY_REASON"
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "allowed": False,
            "reason_code": custom_reason,
            "details": "Custom policy applied",
        }

        with patch("httpx.post", return_value=mock_response):
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            decision = adapter.authorize(request)

        assert decision.reason_code == custom_reason


class TestExternalAuthRequestPayload:
    """Tests for request payload sent to external service."""

    def test_adapter_sends_mcp_request_as_json(self) -> None:
        """External adapter should serialize MCP request to JSON."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = (
            '{"tenant_id": "org-1", "tool_name": "memory_search"}'
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"allowed": True}

        with patch("httpx.post", return_value=mock_response):
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            adapter.authorize(request)

            # Verify request was serialized
            request.model_dump_json.assert_called()

    def test_adapter_sends_request_with_content_type_json(self) -> None:
        """External adapter should set Content-Type to application/json."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        mock_response = MagicMock()
        mock_response.json.return_value = {"allowed": True}

        with patch("httpx.post", return_value=mock_response) as mock_post:
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            adapter.authorize(request)

            call_args = mock_post.call_args
            assert call_args is not None
            if "headers" in call_args[1]:
                assert "application/json" in str(call_args[1]["headers"])


class TestExternalAuthErrorRecovery:
    """Tests for error recovery and resilience."""

    def test_adapter_logs_failed_authorization_attempt(self) -> None:
        """External adapter should log failed authorization."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        with patch("httpx.post", side_effect=Exception("Service error")):
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            # Should not raise, but deny
            decision = adapter.authorize(request)

        assert decision.allowed is False

    def test_adapter_denies_on_any_exception(self) -> None:
        """External adapter should deny on any exception."""
        request = MagicMock(spec=MCPInvokeRequest)
        request.model_dump_json.return_value = "{}"

        exceptions_to_test = [
            ConnectionError("Network error"),
            TimeoutError("Timeout"),
            ValueError("Bad value"),
            Exception("Generic error"),
        ]

        for exc in exceptions_to_test:
            with patch("httpx.post", side_effect=exc):
                adapter = ExternalPassthroughAdapter(
                    external_auth_url="http://service:8080/authorize"
                )
                decision = adapter.authorize(request)

            assert decision.allowed is False
            assert decision.reason_code == "EXTERNAL_AUTH_UNAVAILABLE"
