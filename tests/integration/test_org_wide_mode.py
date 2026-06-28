"""Integration tests for org-wide mode with MCP request injection.

Tests end-to-end org-wide mode behavior including MCP request validation,
tenant ID injection, and cross-mode coexistence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.models.mcp import MCPInvokeRequest, MCPToolName
from src.security.tenant_context import OrgTenantContext
from src.security.validators import validate_tenant_id

if TYPE_CHECKING:
    from src.project_base.settings.config import SingleCompanySettings


class TestOrgWideModeRequestInjection:
    """Tests for tenant_id injection in org-wide mode."""

    def test_mcp_invoke_request_injects_company_id_when_missing(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """MCPInvokeRequest should inject company_id when tenant_id is None."""
        # Create request without tenant_id (simulating unset)
        request = MCPInvokeRequest(
            tenant_id=None,
            tool_name=MCPToolName.MEMORY_SEARCH,
            arguments={"query": "test"},
            session_id="session_1",
            request_id="req_1",
        )

        # In org-wide mode, None should be converted to fixed company_id
        # This happens via the model validator
        assert request.tenant_id == single_company_settings.company_id

    def test_mcp_invoke_request_preserves_tenant_id_when_provided(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """MCPInvokeRequest should preserve matching tenant_id."""
        company_id = single_company_settings.company_id

        request = MCPInvokeRequest(
            tenant_id=company_id,
            tool_name=MCPToolName.MEMORY_SEARCH,
            arguments={"query": "test"},
            session_id="session_1",
            request_id="req_1",
        )

        assert request.tenant_id == company_id

    def test_validate_tenant_id_injects_fixed_value_when_org_wide_enabled(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """validate_tenant_id should inject fixed value when org-wide enabled."""
        result = validate_tenant_id(None)

        assert result == single_company_settings.company_id

    def test_validate_tenant_id_accepts_company_id_when_org_wide_enabled(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """validate_tenant_id should accept company_id when org-wide enabled."""
        result = validate_tenant_id(single_company_settings.company_id)

        assert result == single_company_settings.company_id

    def test_validate_tenant_id_raises_on_mismatch_when_org_wide_enabled(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """validate_tenant_id should raise when input differs from company_id."""
        with pytest.raises(ValueError, match="does not match"):
            validate_tenant_id("different-company")


class TestOrgWideModeValidatorFlow:
    """Tests for validator flow in org-wide mode."""

    def test_org_tenant_context_get_fixed_tenant_id_returns_company_id(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """OrgTenantContext should return company_id when enabled."""
        company_id = OrgTenantContext.get_fixed_tenant_id()

        assert company_id == single_company_settings.company_id

    def test_org_tenant_context_resolve_injects_when_none(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """OrgTenantContext.resolve should inject when input is None."""
        result = OrgTenantContext.resolve(None)

        assert result == single_company_settings.company_id

    def test_org_tenant_context_resolve_accepts_matching_value(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """OrgTenantContext.resolve should accept matching value."""
        company_id = single_company_settings.company_id
        result = OrgTenantContext.resolve(company_id)

        assert result == company_id


class TestSingleCompanySettingsValidation:
    """Tests for SingleCompanySettings validation."""

    def test_settings_requires_company_id_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SingleCompanySettings should require non-empty company_id when enabled."""
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415

        # Should raise validation error
        with pytest.raises(ValueError, match="company_id"):
            SingleCompanySettings(
                enabled=True,
                company_id="",
            )

    def test_settings_allows_blank_company_id_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SingleCompanySettings should allow blank company_id when disabled."""
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415

        settings = SingleCompanySettings(
            enabled=False,
            company_id="",
        )

        assert settings.enabled is False
        assert settings.company_id == ""

    def test_settings_requires_external_url_when_external_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SingleCompanySettings should require external_auth_url when auth_mode='external'."""
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415

        with pytest.raises(ValueError, match="external_auth_url"):
            SingleCompanySettings(
                enabled=True,
                company_id="test-org",
                auth_mode="external",
                external_auth_url=None,
            )

    def test_settings_allows_no_external_url_when_internal_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SingleCompanySettings should allow missing external_auth_url in internal mode."""
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415

        settings = SingleCompanySettings(
            enabled=True,
            company_id="test-org",
            auth_mode="internal",
            external_auth_url=None,
        )

        assert settings.auth_mode == "internal"
        assert settings.external_auth_url is None


class TestOrgWideModeWithFastAPI:
    """Tests for org-wide mode injection in FastAPI request handlers."""

    def test_fastapi_handler_receives_injected_tenant_id(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """FastAPI handler should receive injected tenant_id.

        This test validates the model's injection behavior by omitting
        tenant_id from the request dict and allowing the Pydantic validator
        to populate it from the OrgTenantContext.
        """
        # Simulate an MCP request created by FastAPI endpoint
        request_data = {
            "tool_name": MCPToolName.MEMORY_SEARCH,
            "arguments": {"query": "test"},
            "session_id": "session_1",
            "request_id": "req_1",
        }

        # Create request - model validator should inject tenant_id
        request = MCPInvokeRequest(**request_data)

        assert request.tenant_id == single_company_settings.company_id

    def test_fastapi_handler_validates_injected_tenant_id(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """FastAPI validation should work with injected tenant_id."""
        company_id = single_company_settings.company_id

        # Validate without providing tenant_id
        validated_id = validate_tenant_id(None)

        assert validated_id == company_id


class TestOrgWideModeWithMCPService:
    """Tests for org-wide mode with MCP tool execution."""

    def test_mcp_service_receives_injected_tenant_id(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """MCP service should receive request with injected tenant_id."""
        request = MCPInvokeRequest(
            tenant_id=None,
            tool_name=MCPToolName.MEMORY_SEARCH,
            arguments={"query": "test"},
            session_id="session_1",
            request_id="req_1",
        )

        # Service code can rely on request having tenant_id
        assert request.tenant_id is not None
        assert request.tenant_id == single_company_settings.company_id

    def test_mcp_tool_execution_uses_injected_tenant_id(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """MCP tool should use injected tenant_id for Spanner queries."""
        # Create request with no tenant_id
        request = MCPInvokeRequest(
            tenant_id=None,
            tool_name=MCPToolName.MEMORY_SEARCH,
            arguments={"query": "test"},
            session_id="session_1",
            request_id="req_1",
        )

        # Tool code receives tenant_id
        query_tenant = request.tenant_id

        assert query_tenant == single_company_settings.company_id


class TestSpannerQueryContextWithOrgWideMode:
    """Tests for Spanner query context in org-wide mode."""

    def test_spanner_query_uses_injected_tenant_id(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """Spanner query should use injected tenant_id."""
        request = MCPInvokeRequest(
            tenant_id=None,
            tool_name=MCPToolName.MEMORY_SEARCH,
            arguments={"query": "test"},
            session_id="session_1",
            request_id="req_1",
        )

        # Simulate Spanner query building
        query_params = {
            "tenant_id": request.tenant_id,
            "query": request.arguments["query"],
        }

        assert query_params["tenant_id"] == single_company_settings.company_id
        assert query_params["query"] == "test"


class TestMultiTenantAndOrgWideCoexistence:
    """Tests for multi-tenant mode coexisting with org-wide logic."""

    def test_multi_tenant_mode_requires_explicit_tenant_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Multi-tenant mode should require explicit tenant_id."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415

        multi_tenant = SingleCompanySettings(
            enabled=False,
            company_id="",
        )
        monkeypatch.setattr(settings, "single_company", multi_tenant)

        # Without tenant_id, should fail validation
        with pytest.raises(ValueError, match="must be a non-empty string"):
            validate_tenant_id(None)

    def test_multi_tenant_mode_accepts_any_tenant_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multi-tenant mode should accept any provided tenant_id."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415

        multi_tenant = SingleCompanySettings(
            enabled=False,
            company_id="",
        )
        monkeypatch.setattr(settings, "single_company", multi_tenant)

        result = validate_tenant_id("any-tenant-id")

        assert result == "any-tenant-id"

    def test_handler_can_switch_between_modes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same handler should work in both multi-tenant and org-wide modes."""
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.project_base.settings.config import SingleCompanySettings  # noqa: PLC0415

        # Multi-tenant mode
        multi_tenant = SingleCompanySettings(
            enabled=False,
            company_id="",
        )
        monkeypatch.setattr(settings, "single_company", multi_tenant)
        result_mt = validate_tenant_id("explicit-tenant")
        assert result_mt == "explicit-tenant"

        # Switch to org-wide
        org_wide = SingleCompanySettings(
            enabled=True,
            company_id="org-wide-tenant",
        )
        monkeypatch.setattr(settings, "single_company", org_wide)
        result_ow = validate_tenant_id(None)
        assert result_ow == "org-wide-tenant"

        # Multi-tenant should still work with explicit value
        monkeypatch.setattr(settings, "single_company", multi_tenant)
        result_mt2 = validate_tenant_id("another-tenant")
        assert result_mt2 == "another-tenant"


class TestOrgWideModeModelValidatorOrder:
    """Tests for Pydantic model validator execution order."""

    def test_model_validator_runs_before_field_validation(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """Model validator should inject tenant_id before field validation."""
        # Create request without tenant_id
        request_data = {
            "tool_name": MCPToolName.MEMORY_SEARCH,
            "arguments": {"query": "test"},
            "session_id": "session_1",
            "request_id": "req_1",
        }

        # Should not raise validation error because validator injects tenant_id
        request = MCPInvokeRequest(**request_data)

        assert request.tenant_id is not None

    def test_model_validator_preserves_provided_tenant_id(
        self, single_company_settings: SingleCompanySettings
    ) -> None:
        """Model validator should preserve already-provided tenant_id."""
        company_id = single_company_settings.company_id

        request = MCPInvokeRequest(
            tenant_id=company_id,
            tool_name=MCPToolName.MEMORY_SEARCH,
            arguments={"query": "test"},
            session_id="session_1",
            request_id="req_1",
        )

        assert request.tenant_id == company_id
