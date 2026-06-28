"""Application Settings class; add your settings fields here!

See https://documentation.tryolabs.com/repo-template/batteries/configuration/.

Note: you may store secrets in `.local` or `.env` files.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.security.governance import GovernanceSettings

from ._core import PreconfiguredSettings
from .models import CloudLogging, CloudTrace, Logging


class SingleCompanySettings(BaseModel):
    """Settings for org-wide single-company deployment mode.

    When enabled, the service operates as a managed service for one organisation.
    All requests are scoped to `company_id` without requiring callers to supply a
    `tenant_id`.  Auth can be delegated to the organisation's own policy service
    via `auth_mode = "external"`.
    """

    enabled: bool = False
    """Activate org-wide single-company mode.

    When True, `company_id` is injected as the fixed tenant identifier for every
    request, and callers are no longer required to pass `tenant_id` explicitly.
    Defaults to False.
    """

    company_id: str = Field(default="")
    """Organisation identifier used as `TenantId` across all Spanner tables.

    Must be a non-empty string when `enabled` is True. Defaults to empty string.
    """

    auth_mode: Literal["internal", "external"] = "internal"
    """Authorization mode for this deployment.

    - ``"internal"``: Uses built-in ABAC policy (AuthorizationPolicy).
    - ``"external"``: Delegates authorization decisions to `external_auth_url`.

    Defaults to "internal".
    """

    external_auth_url: str | None = None
    """HTTP URL of the external governance/policy service.

    Required when `auth_mode` is ``"external"``. The service must implement the
    GovernanceAdapter HTTP contract (see docs/deployment/governance-adapter-guide.md).
    Defaults to None.
    """

    @model_validator(mode="after")
    def _validate_company_id_when_enabled(self) -> SingleCompanySettings:
        """Ensure company_id is provided when single-company mode is enabled."""
        if self.enabled and not self.company_id.strip():
            msg = (
                "single_company.company_id must be a non-empty string "
                "when single_company.enabled is True"
            )
            raise ValueError(msg)
        if self.auth_mode == "external" and not self.external_auth_url:
            msg = "single_company.external_auth_url must be set when auth_mode is 'external'"
            raise ValueError(msg)
        return self


class Settings(PreconfiguredSettings):
    """Application settings.

    Sources are loaded with the following priority (highest to lowest):

    - Values passed directly to the constructor (for testing).
    - Environment variables (prefixed with the value of the `ENVIRONMENT_VARIABLE_PREFIX` variable).
    - A `.env` file at the project root.
    - Environment-specific local YAML (`config.{env}.local.yaml`).
    - Environment-specific YAML (`config.{env}.yaml`).
    - Base local YAML (`config.local.yaml`).
    - Base YAML (`config.yaml`).
    - Field default values.
    """

    logging: Logging
    cloud_trace: CloudTrace = CloudTrace()
    cloud_logging: CloudLogging = CloudLogging()
    governance: GovernanceSettings = GovernanceSettings()
    single_company: SingleCompanySettings = SingleCompanySettings()
