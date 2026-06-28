"""Org-wide tenant context for single-company deployment mode.

In single-company (org-wide) mode the service operates with a single fixed
TenantId for all Spanner operations.  This module is the single source of truth
for resolving that identifier at request time, so the injection point is
centralised rather than scattered across every API boundary.

In multi-tenant mode (default) this module is a no-op: callers must supply
`tenant_id` explicitly.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class OrgTenantContext:
    """Resolves the effective tenant identifier for the current deployment mode.

    Reads from ``settings.single_company`` lazily to avoid import-time
    side-effects and to stay testable via fixture overrides.
    """

    @staticmethod
    def get_fixed_tenant_id() -> str | None:
        """Return the fixed company identifier when org-wide mode is active.

        Returns:
            str | None: The configured ``company_id`` when
            ``single_company.enabled`` is ``True``, otherwise ``None``.
        """
        # Lazy import avoids circular imports and settings-load side-effects at
        # module import time.
        from src.project_base.settings import settings  # noqa: PLC0415

        if not settings.single_company.enabled:
            return None
        return settings.single_company.company_id

    @staticmethod
    def resolve(provided_tenant_id: str | None) -> str | None:
        """Resolve the effective tenant identifier from a caller-supplied value.

        In org-wide mode:
        - If ``provided_tenant_id`` is ``None``, returns the fixed company_id.
        - If ``provided_tenant_id`` is supplied but differs from company_id,
          raises ``ValueError`` to prevent cross-tenant confusion.
        - If ``provided_tenant_id`` matches company_id, returns it as-is.

        In multi-tenant mode returns ``provided_tenant_id`` unchanged (may be
        ``None``, in which case the caller's own validation handles the error).

        Args:
            provided_tenant_id: Tenant identifier from the caller, may be None.

        Returns:
            str | None: Resolved tenant identifier.

        Raises:
            ValueError: When org-wide mode is active and the provided value
                conflicts with the configured company_id.
        """
        from src.project_base.settings import settings  # noqa: PLC0415

        if not settings.single_company.enabled:
            return provided_tenant_id

        company_id = settings.single_company.company_id

        if provided_tenant_id is None:
            logger.debug(
                "org_tenant_context_inject",
                extra={"company_id": company_id},
            )
            return company_id

        if provided_tenant_id.strip() != company_id:
            msg = (
                f"tenant_id '{provided_tenant_id}' does not match the configured "
                f"company_id for this deployment"
            )
            raise ValueError(msg)

        return company_id
