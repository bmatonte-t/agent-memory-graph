"""Unit tests for phase-0 governance policy contracts."""

from __future__ import annotations

from src.security.governance import AuthorizationScope, WeightingTriggerPolicy


class TestWeightingTriggerPolicy:
    """Tests for action-count based cognitive weighting triggers."""

    def test_trigger_requires_enabled_policy(self) -> None:
        """Disabled policies should never trigger."""
        policy = WeightingTriggerPolicy(enabled=False, action_count_threshold=3)

        assert policy.should_trigger(100) is False

    def test_trigger_uses_action_threshold(self) -> None:
        """Enabled policies should trigger once the threshold is met."""
        policy = WeightingTriggerPolicy(enabled=True, action_count_threshold=4)

        assert policy.should_trigger(3) is False
        assert policy.should_trigger(4) is True


class TestAuthorizationScope:
    """Tests for ABAC scope contracts."""

    def test_defaults_to_empty_resource_lists(self) -> None:
        """Scopes should default to empty allow-lists."""
        scope = AuthorizationScope(agent_id="agent_1")

        assert scope.agent_id == "agent_1"
        assert scope.allowed_node_ids == []
        assert scope.allowed_labels == []
        assert scope.allowed_memory_tiers == []
        assert scope.allowed_relationship_types == []
