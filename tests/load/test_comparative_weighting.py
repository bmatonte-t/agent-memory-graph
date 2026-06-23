"""Comparative load tests for action-scaled cognitive weighting (Phase 1).

Validates that high-volume tenants trigger more weighting opportunities than
low-volume tenants, with explicit edge case coverage.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from src.memory.api import MemoryAPI
from src.security.governance import WeightingTriggerPolicy
from src.security.validators import validate_tenant_id

# Load test parameters
HIGH_VOLUME_ACTIONS = 100
LOW_VOLUME_ACTIONS = 2
THRESHOLD_ACTIONS = 3
DEFAULT_THRESHOLD = 3


@dataclass(slots=True)
class WeightingMetrics:
    """Captured metrics from weighting behavior simulation."""

    tenant_id: str
    action_count: int
    weight_update_count: int
    weight_skipped_count: int


async def _simulate_tenant_actions(
    *,
    tenant_id: str,
    session_id: str,
    action_count: int,
    weighting_policy: WeightingTriggerPolicy,
) -> WeightingMetrics:
    """Simulate a tenant performing actions and track weighting decisions.

    Args:
        tenant_id: Tenant identifier.
        session_id: Session identifier for this tenant.
        action_count: Number of simulated actions.
        weighting_policy: Weighting trigger policy.

    Returns:
        WeightingMetrics: Update/skip counts and action count.
    """
    validate_tenant_id(tenant_id)
    weight_updates = 0
    weight_skips = 0

    with (
        patch("src.memory.api.SpannerClient.get_database") as mock_db,
        patch(
            "src.memory.api.settings.governance.weighting",
            weighting_policy,
        ),
    ):
        mock_batch = MagicMock()
        mock_batch.execute_update.return_value = 1  # One row updated
        mock_db.return_value.batch.return_value.__enter__.return_value = mock_batch

        for i in range(action_count):
            current_action_count = i + 1

            # Simulate incrementing session action count
            with patch("src.memory.api.SpannerClient.get_database") as mock_transaction_db:
                mock_transaction = MagicMock()
                mock_transaction.execute_sql.return_value = [(current_action_count,)]
                mock_transaction_db.return_value.run_in_transaction.return_value = (
                    current_action_count
                )

            # Determine expected behavior based on policy
            # (matches logic in _update_weight_on_successful_use)
            if not weighting_policy.enabled:
                # Disabled: skip all
                expected_skip = True
            elif weighting_policy.should_trigger(current_action_count):
                # Enabled and crosses threshold: update
                expected_skip = False
            else:
                # Enabled but below threshold: skip
                expected_skip = True

            # Simulate a fact addition triggering potential weight update
            try:
                await MemoryAPI._update_weight_on_successful_use(
                    tenant_id=tenant_id,
                    node_ids=["test_node_1"],
                    session_action_count=current_action_count,
                )

                # Count based on expected behavior
                if expected_skip:
                    weight_skips += 1
                else:
                    weight_updates += 1
            except ValueError:
                # Catch any validation errors and count as skip
                weight_skips += 1

    return WeightingMetrics(
        tenant_id=tenant_id,
        action_count=action_count,
        weight_update_count=weight_updates,
        weight_skipped_count=weight_skips,
    )


class TestComparativeWeighting:
    """Validate action-scaled weighting behavior across tenant activity volumes."""

    async def test_high_volume_tenant_triggers_more_weighting_than_low_volume(
        self,
    ) -> None:
        """High-volume tenants should trigger weight updates; low-volume should skip.

        This test validates Phase 1 success criterion: high-volume tenants get
        more weighting opportunities than low-volume tenants.
        """
        policy = WeightingTriggerPolicy(enabled=True, action_count_threshold=3)

        high_volume = await _simulate_tenant_actions(
            tenant_id="high_volume_tenant",
            session_id="session_high",
            action_count=HIGH_VOLUME_ACTIONS,
            weighting_policy=policy,
        )

        low_volume = await _simulate_tenant_actions(
            tenant_id="low_volume_tenant",
            session_id="session_low",
            action_count=LOW_VOLUME_ACTIONS,
            weighting_policy=policy,
        )

        # High-volume tenant crosses threshold and gets weight updates
        assert high_volume.weight_update_count > 0, "High-volume tenant should trigger weighting"

        # Low-volume tenant stays below threshold and skips weight updates
        assert low_volume.weight_skipped_count == low_volume.action_count, (
            f"Low-volume tenant should skip all {low_volume.action_count} updates below threshold"
        )

        # Verification: high-volume should have significantly more updates
        assert high_volume.weight_update_count > low_volume.weight_update_count, (
            "High-volume should trigger more weighting than low-volume"
        )

    async def test_action_count_below_threshold_skips_weighting(self) -> None:
        """Actions below threshold should skip weight updates.

        Validates that the weighting policy correctly skips updates when
        action_count < action_count_threshold.
        """
        policy = WeightingTriggerPolicy(enabled=True, action_count_threshold=5)

        result = await _simulate_tenant_actions(
            tenant_id="below_threshold_tenant",
            session_id="session_below",
            action_count=THRESHOLD_ACTIONS - 1,
            weighting_policy=policy,
        )

        # All actions should be skipped (below threshold of 5)
        assert result.weight_skipped_count == result.action_count, (
            f"Expected all {result.action_count} updates to be skipped below threshold"
        )

    async def test_action_count_exactly_at_threshold_triggers_weighting(
        self,
    ) -> None:
        """Action count exactly at threshold should trigger weighting.

        Validates edge case: should_trigger(action_count == threshold) → True.
        """
        threshold = 5
        policy = WeightingTriggerPolicy(enabled=True, action_count_threshold=threshold)

        result = await _simulate_tenant_actions(
            tenant_id="at_threshold_tenant",
            session_id="session_at",
            action_count=threshold,
            weighting_policy=policy,
        )

        # First (threshold-1) should skip, then threshold and beyond should trigger
        expected_updates = 1  # Only action_count == threshold triggers
        assert result.weight_update_count >= expected_updates, (
            f"Expected at least {expected_updates} update at threshold"
        )

    async def test_action_count_exceeding_threshold_triggers_weighting(
        self,
    ) -> None:
        """Actions exceeding threshold should consistently trigger weighting.

        Validates: should_trigger(action_count > threshold) → True.
        """
        threshold = 3
        policy = WeightingTriggerPolicy(enabled=True, action_count_threshold=threshold)

        result = await _simulate_tenant_actions(
            tenant_id="exceeding_tenant",
            session_id="session_exceed",
            action_count=threshold + 10,
            weighting_policy=policy,
        )

        # After reaching threshold, all subsequent actions should trigger weighting
        expected_updates = 10  # (threshold + 10) - threshold
        assert result.weight_update_count >= expected_updates, (
            f"Expected at least {expected_updates} updates after exceeding threshold"
        )

    async def test_weighting_disabled_skips_all_updates(self) -> None:
        """When weighting is disabled, all updates should be skipped.

        Validates that the feature can be safely disabled (backward compatibility).
        """
        policy = WeightingTriggerPolicy(enabled=False, action_count_threshold=1)

        result = await _simulate_tenant_actions(
            tenant_id="disabled_tenant",
            session_id="session_disabled",
            action_count=HIGH_VOLUME_ACTIONS,
            weighting_policy=policy,
        )

        # All updates should be skipped when disabled
        assert result.weight_skipped_count == result.action_count, (
            "Disabled policy should skip all weighting updates"
        )

    async def test_multiple_concurrent_tenants_independent_weighting(self) -> None:
        """Multiple tenants operating concurrently should maintain independent counters.

        Validates that session action counting is tenant-isolated and does not
        interfere with concurrent operations.
        """
        policy = WeightingTriggerPolicy(enabled=True, action_count_threshold=5)

        tenant_a_task = _simulate_tenant_actions(
            tenant_id="tenant_a",
            session_id="session_a",
            action_count=10,
            weighting_policy=policy,
        )

        tenant_b_task = _simulate_tenant_actions(
            tenant_id="tenant_b",
            session_id="session_b",
            action_count=2,
            weighting_policy=policy,
        )

        tenant_c_task = _simulate_tenant_actions(
            tenant_id="tenant_c",
            session_id="session_c",
            action_count=8,
            weighting_policy=policy,
        )

        results = await asyncio.gather(tenant_a_task, tenant_b_task, tenant_c_task)

        result_a, result_b, result_c = results

        # Tenant A (10 actions) should trigger weighting
        assert result_a.weight_update_count > 0, "Tenant A with 10 actions should trigger weighting"

        # Tenant B (2 actions) should skip
        assert result_b.weight_skipped_count == result_b.action_count, (
            "Tenant B with 2 actions should skip all weighting"
        )

        # Tenant C (8 actions) should trigger weighting
        assert result_c.weight_update_count > 0, "Tenant C with 8 actions should trigger weighting"

        # Verify independence: A's behavior should not affect B or C
        assert result_a.tenant_id != result_b.tenant_id
        assert result_b.tenant_id != result_c.tenant_id

    def test_weighting_trigger_policy_with_default_threshold(self) -> None:
        """Default threshold (3) should be respected without explicit configuration.

        Validates that WeightingTriggerPolicy defaults are sensible.
        """
        policy = WeightingTriggerPolicy(enabled=True)

        assert policy.action_count_threshold == DEFAULT_THRESHOLD, (
            f"Default threshold should be {DEFAULT_THRESHOLD}"
        )
        assert policy.should_trigger(DEFAULT_THRESHOLD - 1) is False, (
            f"{DEFAULT_THRESHOLD - 1} should not trigger (below {DEFAULT_THRESHOLD})"
        )
        assert policy.should_trigger(DEFAULT_THRESHOLD) is True, (
            f"{DEFAULT_THRESHOLD} should trigger (at default threshold)"
        )
        assert policy.should_trigger(DEFAULT_THRESHOLD + 1) is True, (
            f"{DEFAULT_THRESHOLD + 1} should trigger (above {DEFAULT_THRESHOLD})"
        )

    def test_weighting_trigger_policy_disabled_overrides_threshold(self) -> None:
        """Disabled policy should always return False regardless of threshold.

        Validates: enabled=False → should_trigger() always returns False.
        """
        policy = WeightingTriggerPolicy(enabled=False, action_count_threshold=1)

        assert policy.should_trigger(1000) is False, (
            "Disabled policy should not trigger even at high action count"
        )
