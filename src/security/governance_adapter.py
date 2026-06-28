"""Pluggable governance adapters for MCP authorization.

This module defines the ``GovernanceAdapter`` protocol and two concrete
implementations:

- ``InternalAbacAdapter``: Uses the built-in ABAC policy (``AuthorizationPolicy``
  + ``AuthorizationScope``).  This is the default for all deployments.
- ``ExternalPassthroughAdapter``: Delegates the authorization decision to an
  HTTP policy service operated by the customer.  Used when the client already
  has an established auth/governance layer and we should not duplicate it.

Selecting an adapter is done via ``settings.single_company.auth_mode``.  The
factory function ``build_governance_adapter()`` reads this at call time so it
can be overridden in tests without module-level side-effects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from src.models.mcp import MCPInvokeRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared data contract
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AuthorizationDecision:
    """Result of an authorization check.

    Attributes:
        allowed: Whether the request is permitted.
        reason_code: Machine-readable reason for the decision
            (e.g., ``"AUTHORIZED_AGENT_SCOPE"``, ``"DENIED_EXTERNAL_POLICY"``).
        details: Optional human-readable details for logging.
    """

    allowed: bool
    reason_code: str
    details: str | None = None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class GovernanceAdapter(Protocol):
    """Protocol that all authorization adapters must satisfy.

    Implementations decide whether an ``MCPInvokeRequest`` should be allowed to
    proceed.  Callers receive an ``AuthorizationDecision`` and must not proceed
    when ``allowed`` is ``False``.
    """

    def authorize(self, request: MCPInvokeRequest) -> AuthorizationDecision:
        """Evaluate whether the request is authorized.

        Args:
            request: The incoming MCP tool invocation request.

        Returns:
            AuthorizationDecision: Decision with reason code and optional details.
        """
        ...


# ---------------------------------------------------------------------------
# Internal ABAC adapter (default)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class InternalAbacAdapter:
    """Authorization adapter backed by the built-in ABAC policy.

    Wraps ``AuthorizationPolicy.authorize()`` and the ``AuthorizationScope``
    resource-check logic that was previously inline in ``MCPToolService``.
    """

    def authorize(self, request: MCPInvokeRequest) -> AuthorizationDecision:
        """Evaluate the request using the built-in ABAC policy.

        Args:
            request: The incoming MCP tool invocation request.

        Returns:
            AuthorizationDecision: Decision based on scope and configured policy.
        """
        from src.models.mcp import MCPToolName  # noqa: PLC0415
        from src.project_base.settings import settings  # noqa: PLC0415
        from src.security.validators import validate_relationship  # noqa: PLC0415

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
            from typing import cast  # noqa: PLC0415

            entity_id = request.arguments.get("entity_id")
            entity_type = request.arguments.get("entity_type")
            relationship = request.arguments.get("relationship")
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

        if request.tool_name not in (
            MCPToolName.MEMORY_SEARCH,
            MCPToolName.MEMORY_ADD_FACT,
            MCPToolName.MEMORY_LOG_TRACE,
            MCPToolName.MEMORY_RECALL_CONTEXT,
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


# ---------------------------------------------------------------------------
# External passthrough adapter
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ExternalPassthroughAdapter:
    """Authorization adapter that delegates decisions to a customer policy service.

    The service at ``external_auth_url`` must implement the GovernanceAdapter
    HTTP contract described in ``docs/deployment/governance-adapter-guide.md``.
    A ``POST`` request is sent with the serialized ``MCPInvokeRequest``; the
    response is expected to contain ``{"allowed": bool, "reason_code": str}``.

    Network failures are treated as authorization denials with reason code
    ``"EXTERNAL_AUTH_UNAVAILABLE"`` so that a degraded policy service does not
    silently become an open gate.

    Attributes:
        external_auth_url: URL of the customer's policy service.
    """

    external_auth_url: str
    _request_timeout_seconds: float = field(default=5.0, repr=False)

    def authorize(self, request: MCPInvokeRequest) -> AuthorizationDecision:
        """Delegate the authorization decision to the external policy service.

        Args:
            request: The incoming MCP tool invocation request.

        Returns:
            AuthorizationDecision: Decision returned by the external service,
            or a denial if the service is unreachable.
        """
        try:
            import httpx  # noqa: PLC0415
        except ImportError:
            logger.exception(
                "external_auth_adapter_missing_httpx",
                extra={"external_auth_url": self.external_auth_url},
            )
            return AuthorizationDecision(
                allowed=False,
                reason_code="EXTERNAL_AUTH_DEPENDENCY_MISSING",
                details="httpx is required for ExternalPassthroughAdapter; add it to dependencies",
            )

        try:
            response = httpx.post(
                self.external_auth_url,
                content=request.model_dump_json(),
                headers={"Content-Type": "application/json"},
                timeout=self._request_timeout_seconds,
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            return AuthorizationDecision(
                allowed=bool(payload.get("allowed", False)),
                reason_code=str(payload.get("reason_code", "EXTERNAL_DECISION")),
                details=str(payload.get("details", "")),
            )
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "external_auth_adapter_failure",
                extra={
                    "external_auth_url": self.external_auth_url,
                    "error": str(error),
                },
            )
            return AuthorizationDecision(
                allowed=False,
                reason_code="EXTERNAL_AUTH_UNAVAILABLE",
                details=f"Policy service unreachable: {error}",
            )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_ADAPTER_CACHE: dict[str, GovernanceAdapter] = {}
"""Module-level cache so the adapter is built once per process.

Tests should clear this dict when overriding settings via fixtures.
"""


def build_governance_adapter() -> GovernanceAdapter:
    """Return the governance adapter configured for the current deployment.

    Reads ``settings.single_company.auth_mode`` to select the implementation.
    The result is cached so expensive HTTP configuration is not repeated on
    every MCP call.  Tests that need a fresh adapter should call
    ``_ADAPTER_CACHE.clear()`` before the request under test.

    Returns:
        GovernanceAdapter: Configured adapter instance.
    """
    from src.project_base.settings import settings  # noqa: PLC0415

    auth_mode = settings.single_company.auth_mode if settings.single_company.enabled else "internal"

    if auth_mode not in _ADAPTER_CACHE:
        if auth_mode == "external":
            external_url = settings.single_company.external_auth_url or ""
            _ADAPTER_CACHE[auth_mode] = ExternalPassthroughAdapter(external_auth_url=external_url)
            logger.info(
                "governance_adapter_built",
                extra={"auth_mode": auth_mode, "external_auth_url": external_url},
            )
        else:
            _ADAPTER_CACHE[auth_mode] = InternalAbacAdapter()
            logger.info("governance_adapter_built", extra={"auth_mode": auth_mode})

    return _ADAPTER_CACHE[auth_mode]
