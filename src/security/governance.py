"""Governance contracts for phase-0 weighting and authorization policy."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WeightingTriggerPolicy(BaseModel):
    """Policy for triggering cognitive weighting from agent activity volume."""

    enabled: bool = False
    action_count_threshold: int = Field(default=3, ge=1)

    def should_trigger(self, action_count: int) -> bool:
        """Return whether the current action count crosses the configured threshold."""
        return self.enabled and action_count >= self.action_count_threshold


class AuthorizationScope(BaseModel):
    """Agent-scoped access predicate used for future ABAC enforcement."""

    agent_id: str = Field(..., min_length=1)
    allowed_node_ids: list[str] = Field(default_factory=list)
    allowed_labels: list[str] = Field(default_factory=list)
    allowed_memory_tiers: list[str] = Field(default_factory=list)
    allowed_relationship_types: list[str] = Field(default_factory=list)

    def allows_resource(
        self,
        *,
        node_id: str | None = None,
        label: str | None = None,
        memory_tier: str | None = None,
        relationship_type: str | None = None,
    ) -> bool:
        """Return whether the scope permits access to the requested resource."""
        configured_dimensions = 0

        if self.allowed_node_ids:
            configured_dimensions += 1
            if node_id is None or node_id not in self.allowed_node_ids:
                return False

        if self.allowed_labels:
            configured_dimensions += 1
            if label is None or label not in self.allowed_labels:
                return False

        if self.allowed_memory_tiers:
            configured_dimensions += 1
            if memory_tier is None or memory_tier not in self.allowed_memory_tiers:
                return False

        if self.allowed_relationship_types:
            configured_dimensions += 1
            if (
                relationship_type is None
                or relationship_type not in self.allowed_relationship_types
            ):
                return False

        return configured_dimensions > 0


class RetryPolicy(BaseModel):
    """Retry policy used to define phase-0 write resilience defaults."""

    max_attempts: int = Field(default=3, ge=1)
    initial_backoff_seconds: float = Field(default=0.25, gt=0.0)
    max_backoff_seconds: float = Field(default=5.0, gt=0.0)


class AuthorizationPolicy(BaseModel):
    """Global authorization feature flags and safety defaults."""

    enabled: bool = False
    default_deny: bool = True

    def authorize(
        self,
        scope: AuthorizationScope | None,
        *,
        node_id: str | None = None,
        label: str | None = None,
        memory_tier: str | None = None,
        relationship_type: str | None = None,
    ) -> bool:
        """Evaluate whether the supplied scope is authorized for a resource."""
        if not self.enabled:
            return True
        if scope is None:
            return not self.default_deny
        return scope.allows_resource(
            node_id=node_id,
            label=label,
            memory_tier=memory_tier,
            relationship_type=relationship_type,
        )


class GovernanceSettings(BaseModel):
    """Top-level governance settings for phase-0 decision freeze."""

    weighting: WeightingTriggerPolicy = Field(default_factory=WeightingTriggerPolicy)
    authorization: AuthorizationPolicy = Field(default_factory=AuthorizationPolicy)
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
