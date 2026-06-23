"""Unit tests for phase-0 governance policy contracts."""

from __future__ import annotations

from src.security.governance import (
    AuthorizationPolicy,
    AuthorizationScope,
    WeightingTriggerPolicy,
)


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

    def test_empty_scope_denies_all_resources(self) -> None:
        """Empty scopes (all dimensions empty) should deny access to all resources."""
        scope = AuthorizationScope(agent_id="agent_1")

        assert scope.allows_resource(node_id="entity_1") is False
        assert scope.allows_resource(label="PERSON") is False
        assert scope.allows_resource(memory_tier="SEMANTIC") is False
        assert scope.allows_resource(relationship_type="REFERENCES") is False
        assert (
            scope.allows_resource(
                node_id="entity_1",
                label="PERSON",
                memory_tier="SEMANTIC",
                relationship_type="REFERENCES",
            )
            is False
        )

    def test_configured_node_ids_allow_matching_nodes(self) -> None:
        """Configured node_ids should allow only matching nodes."""
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1", "entity_2"],
        )

        assert scope.allows_resource(node_id="entity_1") is True
        assert scope.allows_resource(node_id="entity_2") is True
        assert scope.allows_resource(node_id="entity_3") is False

    def test_configured_labels_allow_matching_labels(self) -> None:
        """Configured labels should allow only matching labels."""
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_labels=["PERSON", "ORGANIZATION"],
        )

        assert scope.allows_resource(label="PERSON") is True
        assert scope.allows_resource(label="ORGANIZATION") is True
        assert scope.allows_resource(label="OBJECT") is False

    def test_multiple_dimensions_require_all_to_match(self) -> None:
        """All configured dimensions must match for access to be granted."""
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1"],
            allowed_labels=["PERSON"],
        )

        # Node matches but label missing
        assert scope.allows_resource(node_id="entity_1", label=None) is False
        # Node matches but label doesn't
        assert scope.allows_resource(node_id="entity_1", label="OBJECT") is False
        # Both match
        assert scope.allows_resource(node_id="entity_1", label="PERSON") is True


class TestAuthorizationPolicy:
    """Tests for authorization policy enforcement."""

    def test_disabled_policy_allows_all_resources(self) -> None:
        """Disabled authorization should allow all resources."""
        policy = AuthorizationPolicy(enabled=False, default_deny=True)
        scope = AuthorizationScope(agent_id="agent_1")  # Empty scope

        assert policy.authorize(scope, node_id="entity_1") is True

    def test_missing_scope_with_default_deny_denies(self) -> None:
        """Missing scope with default_deny=true should deny."""
        policy = AuthorizationPolicy(enabled=True, default_deny=True)

        assert policy.authorize(None, node_id="entity_1") is False

    def test_missing_scope_without_default_deny_allows(self) -> None:
        """Missing scope with default_deny=false should allow."""
        policy = AuthorizationPolicy(enabled=True, default_deny=False)

        assert policy.authorize(None, node_id="entity_1") is True

    def test_policy_delegates_to_scope(self) -> None:
        """Policy should delegate to scope.allows_resource when scope provided."""
        policy = AuthorizationPolicy(enabled=True, default_deny=True)
        scope = AuthorizationScope(
            agent_id="agent_1",
            allowed_node_ids=["entity_1"],
        )

        assert policy.authorize(scope, node_id="entity_1") is True
        assert policy.authorize(scope, node_id="entity_2") is False
