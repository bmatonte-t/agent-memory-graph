"""Integration tests for ExternalPassthroughAdapter with real-like scenarios.

Tests the HTTP delegation pattern for authorization to external policy services,
including error handling, timeouts, and policy response validation.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

from src.security.governance_adapter import (
    AuthorizationDecision,
    ExternalPassthroughAdapter,
    build_governance_adapter,
)

# Constant for external auth adapter timeout validation
EXTERNAL_AUTH_TIMEOUT_SECONDS = 5.0


@contextmanager
def _override_httpx_post(post_impl: Callable[..., object]) -> Iterator[None]:
    """Temporarily override ``httpx.post`` for deterministic adapter tests."""
    original_post = httpx.post
    httpx.post = post_impl
    try:
        yield
    finally:
        httpx.post = original_post


class _RequestStub:
    """MCP request stub with deterministic JSON serialization behavior."""

    def __init__(self, payload_json: str = "{}") -> None:
        """Initialize request payload.

        Args:
            payload_json: JSON payload returned by model_dump_json.
        """
        self.payload_json = payload_json
        self.model_dump_json_calls = 0

    def model_dump_json(self) -> str:
        """Return serialized request payload.

        Returns:
            str: Request payload JSON.
        """
        self.model_dump_json_calls += 1
        return self.payload_json


class _ResponseStub:
    """HTTP response stub for external authorization adapter tests."""

    def __init__(self, payload: dict[str, object], *, json_error: Exception | None = None) -> None:
        """Initialize response payload and optional JSON parsing error.

        Args:
            payload: Payload returned by json().
            json_error: Optional exception raised by json().
        """
        self._payload = payload
        self._json_error = json_error

    def raise_for_status(self) -> None:
        """No-op status validation for successful stubs."""

    def json(self) -> dict[str, object]:
        """Return payload or raise configured parsing error.

        Returns:
            dict[str, object]: Parsed payload.
        """
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class TestExternalAuthAdapterIntegration:
    """Tests for ExternalPassthroughAdapter in realistic scenarios."""

    def test_adapter_handles_policy_service_approval(self) -> None:
        """External adapter should authorize based on policy service response."""
        request = _RequestStub()

        response = _ResponseStub(
            {
                "allowed": True,
                "reason_code": "POLICY_APPROVED",
                "details": "User has required scope",
            }
        )

        def _post_stub(*_: object, **__: object) -> _ResponseStub:
            return response

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://policy-service:8080/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is True
        assert decision.reason_code == "POLICY_APPROVED"

    def test_adapter_handles_policy_service_denial(self) -> None:
        """External adapter should deny based on policy service response."""
        request = _RequestStub()

        response = _ResponseStub(
            {
                "allowed": False,
                "reason_code": "INSUFFICIENT_SCOPE",
                "details": "User scope does not include memory_search",
            }
        )

        def _post_stub(*_: object, **__: object) -> _ResponseStub:
            return response

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://policy-service:8080/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "INSUFFICIENT_SCOPE"
        assert "memory_search" in decision.details

    def test_adapter_sends_request_to_correct_endpoint(self) -> None:
        """External adapter should POST to the configured service URL."""
        request = _RequestStub(payload_json='{"tool": "memory_search"}')

        response = _ResponseStub({"allowed": True})

        called_urls: list[str] = []

        def _post_stub(url: str, **_: object) -> _ResponseStub:
            called_urls.append(url)
            return response

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://localhost:8001/authorize"
            )
            adapter.authorize(request)

            # Verify post was called with correct URL and timeout
            assert called_urls == ["http://localhost:8001/authorize"]

    def test_adapter_includes_timeout_in_request(self) -> None:
        """External adapter should respect timeout configuration."""
        request = _RequestStub()

        response = _ResponseStub({"allowed": True})

        observed_timeout: list[float] = []

        def _post_stub(url: str, **kwargs: object) -> _ResponseStub:
            del url
            timeout_value = kwargs.get("timeout")
            if isinstance(timeout_value, int | float):
                observed_timeout.append(float(timeout_value))
            return response

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://localhost:8001/authorize",
                _request_timeout_seconds=5.0,
            )
            adapter.authorize(request)

            # Verify timeout was passed
            assert observed_timeout == [EXTERNAL_AUTH_TIMEOUT_SECONDS]

    def test_adapter_recovers_from_network_error(self) -> None:
        """External adapter should deny on network errors."""
        request = _RequestStub()

        def _post_stub(*_: object, **__: object) -> _ResponseStub:
            msg = "Network unreachable"
            raise ConnectionError(msg)

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://unreachable-service:8080/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "EXTERNAL_AUTH_UNAVAILABLE"

    def test_adapter_recovers_from_service_timeout(self) -> None:
        """External adapter should deny on timeout."""
        request = _RequestStub()

        def _post_stub(*_: object, **__: object) -> _ResponseStub:
            msg = "Request timeout"
            raise TimeoutError(msg)

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://slow-service:8080/authorize",
                _request_timeout_seconds=1.0,
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "EXTERNAL_AUTH_UNAVAILABLE"

    def test_adapter_handles_json_parse_error(self) -> None:
        """External adapter should deny on malformed JSON response."""
        request = _RequestStub()

        response = _ResponseStub({}, json_error=ValueError("Invalid JSON"))

        def _post_stub(*_: object, **__: object) -> _ResponseStub:
            return response

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(
                external_auth_url="http://buggy-service:8080/authorize"
            )
            decision = adapter.authorize(request)

        assert decision.allowed is False
        assert decision.reason_code == "EXTERNAL_AUTH_UNAVAILABLE"


class TestExternalAuthFactoryIntegration:
    """Tests for governance adapter factory with external auth."""

    def test_factory_creates_external_adapter_in_external_mode(self) -> None:
        """Factory should create ExternalPassthroughAdapter when configured."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415
        from src.security import governance_adapter  # noqa: PLC0415

        original_single_company = settings.single_company
        org_settings = SingleCompanySettings(
            enabled=True,
            company_id="org-1",
            auth_mode="external",
            external_auth_url="http://policy-service:8080/authorize",
        )
        settings.single_company = org_settings
        governance_adapter._ADAPTER_CACHE.clear()

        try:
            adapter = build_governance_adapter()

            assert isinstance(adapter, ExternalPassthroughAdapter)
            assert adapter.external_auth_url == "http://policy-service:8080/authorize"
        finally:
            settings.single_company = original_single_company
            governance_adapter._ADAPTER_CACHE.clear()

    def test_factory_caches_external_adapter(self) -> None:
        """Factory should cache the external adapter instance."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415
        from src.security import governance_adapter  # noqa: PLC0415

        original_single_company = settings.single_company
        org_settings = SingleCompanySettings(
            enabled=True,
            company_id="org-1",
            auth_mode="external",
            external_auth_url="http://policy-service:8080/authorize",
        )
        settings.single_company = org_settings
        governance_adapter._ADAPTER_CACHE.clear()

        try:
            adapter_1 = build_governance_adapter()
            adapter_2 = build_governance_adapter()

            assert adapter_1 is adapter_2
        finally:
            settings.single_company = original_single_company
            governance_adapter._ADAPTER_CACHE.clear()

    def test_factory_invalidates_cache_on_url_change(self) -> None:
        """Factory should create new adapter when URL changes."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import (  # noqa: PLC0415
            SingleCompanySettings,
        )
        from src.security import governance_adapter  # noqa: PLC0415

        original_single_company = settings.single_company
        org_settings_1 = SingleCompanySettings(
            enabled=True,
            company_id="org-1",
            auth_mode="external",
            external_auth_url="http://service-1:8080/authorize",
        )
        settings.single_company = org_settings_1
        governance_adapter._ADAPTER_CACHE.clear()

        try:
            adapter_1 = build_governance_adapter()

            org_settings_2 = SingleCompanySettings(
                enabled=True,
                company_id="org-1",
                auth_mode="external",
                external_auth_url="http://service-2:8080/authorize",
            )
            settings.single_company = org_settings_2
            governance_adapter._ADAPTER_CACHE.clear()

            adapter_2 = build_governance_adapter()

            assert adapter_1 is not adapter_2
            assert adapter_1.external_auth_url == "http://service-1:8080/authorize"
            assert adapter_2.external_auth_url == "http://service-2:8080/authorize"
        finally:
            settings.single_company = original_single_company
            governance_adapter._ADAPTER_CACHE.clear()


class TestExternalAuthPolicyResponseValidation:
    """Tests for validating policy service responses."""

    def test_adapter_accepts_response_with_all_fields(self) -> None:
        """Adapter should accept complete policy response."""
        request = _RequestStub()

        response = _ResponseStub(
            {
                "allowed": True,
                "reason_code": "COMPLETE_RESPONSE",
                "details": "All fields present",
            }
        )

        def _post_stub(*_: object, **__: object) -> _ResponseStub:
            return response

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            decision = adapter.authorize(request)

        assert isinstance(decision, AuthorizationDecision)
        assert decision.allowed is True
        assert decision.reason_code == "COMPLETE_RESPONSE"

    def test_adapter_defaults_allowed_to_false(self) -> None:
        """Adapter should default allowed to False if missing from response."""
        request = _RequestStub()

        response = _ResponseStub({"reason_code": "PARTIAL_RESPONSE"})

        def _post_stub(*_: object, **__: object) -> _ResponseStub:
            return response

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            decision = adapter.authorize(request)

        assert decision.allowed is False

    def test_adapter_accepts_reason_code_from_policy_service(self) -> None:
        """Adapter should preserve reason_code from policy service."""
        request = _RequestStub()

        custom_reason = "CUSTOM_POLICY_REASON"
        response = _ResponseStub(
            {
                "allowed": False,
                "reason_code": custom_reason,
                "details": "Custom policy applied",
            }
        )

        def _post_stub(*_: object, **__: object) -> _ResponseStub:
            return response

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            decision = adapter.authorize(request)

        assert decision.reason_code == custom_reason


class TestExternalAuthRequestPayload:
    """Tests for request payload sent to external service."""

    def test_adapter_sends_mcp_request_as_json(self) -> None:
        """External adapter should serialize MCP request to JSON."""
        request = _RequestStub(
            payload_json=('{"tenant_id": "org-1", "tool_name": "memory_search"}')
        )

        response = _ResponseStub({"allowed": True})

        def _post_stub(*_: object, **__: object) -> _ResponseStub:
            return response

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            adapter.authorize(request)

            # Verify request was serialized
            assert request.model_dump_json_calls == 1

    def test_adapter_sends_request_with_content_type_json(self) -> None:
        """External adapter should set Content-Type to application/json."""
        request = _RequestStub()

        response = _ResponseStub({"allowed": True})

        observed_headers: list[object] = []

        def _post_stub(url: str, **kwargs: object) -> _ResponseStub:
            del url
            observed_headers.append(kwargs.get("headers"))
            return response

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            adapter.authorize(request)

            assert observed_headers
            assert "application/json" in str(observed_headers[0])


class TestExternalAuthErrorRecovery:
    """Tests for error recovery and resilience."""

    def test_adapter_logs_failed_authorization_attempt(self) -> None:
        """External adapter should log failed authorization."""
        request = _RequestStub()

        def _post_stub(*_: object, **__: object) -> _ResponseStub:
            msg = "Service error"
            raise RuntimeError(msg)

        with _override_httpx_post(_post_stub):
            adapter = ExternalPassthroughAdapter(external_auth_url="http://service:8080/authorize")
            # Should not raise, but deny
            decision = adapter.authorize(request)

        assert decision.allowed is False

    def test_adapter_denies_on_any_exception(self) -> None:
        """External adapter should deny on any exception."""
        request = _RequestStub()

        exceptions_to_test = [
            ConnectionError("Network error"),
            TimeoutError("Timeout"),
            ValueError("Bad value"),
            Exception("Generic error"),
        ]

        for exc in exceptions_to_test:

            def _post_stub(
                *_: object,
                __error: Exception = exc,
                **__: object,
            ) -> _ResponseStub:
                raise __error

            with _override_httpx_post(_post_stub):
                adapter = ExternalPassthroughAdapter(
                    external_auth_url="http://service:8080/authorize"
                )
                decision = adapter.authorize(request)

            assert decision.allowed is False
            assert decision.reason_code == "EXTERNAL_AUTH_UNAVAILABLE"
