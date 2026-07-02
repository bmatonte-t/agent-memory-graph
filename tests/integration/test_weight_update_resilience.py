"""Integration tests for weight update retry resilience."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import src.memory.api as memory_api
from src.memory.api import MemoryAPI

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

TENANT_ID = "tenant_123"
TEST_NODE_IDS = ["node_1", "node_2", "node_3"]


@dataclass(slots=True)
class _RetryPolicyStub:
    """Simple retry policy test double."""

    max_attempts: int = 1
    initial_backoff_seconds: float = 0.0
    max_backoff_seconds: float = 0.0


@dataclass(slots=True)
class _WeightingPolicyStub:
    """Simple weighting policy test double."""

    enabled: bool
    should_trigger_result: bool = True
    action_count_threshold: int = 1

    def should_trigger(self, _: int) -> bool:
        """Return the configured trigger behavior."""
        return self.should_trigger_result


class _BatchStub:
    """Batch test double that tracks update calls."""

    def __init__(self) -> None:
        self.execute_update_calls = 0

    def execute_update(self, _: str, __: dict[str, object]) -> None:
        """Record update invocations."""
        self.execute_update_calls += 1


class _BatchContext:
    """Context manager around the batch test double."""

    def __init__(self, batch: _BatchStub) -> None:
        self._batch = batch

    def __enter__(self) -> _BatchStub:
        """Return batch stub on context entry."""
        return self._batch

    def __exit__(
        self,
        _: type[BaseException] | None,
        __: BaseException | None,
        ___: TracebackType | None,
    ) -> bool:
        """Allow exception propagation from write path."""
        return False


class _DatabaseStub:
    """Database test double exposing batch context manager."""

    def __init__(self, batch: _BatchStub) -> None:
        self._batch = batch

    def batch(self) -> _BatchContext:
        """Return context manager for batch operations."""
        return _BatchContext(self._batch)


class _SpannerClientStub:
    """Client test double returning the configured database."""

    database: _DatabaseStub | None = None

    @classmethod
    def get_database(cls) -> _DatabaseStub:
        """Return configured database stub."""
        if cls.database is None:
            msg = "Database stub was not configured"
            raise RuntimeError(msg)
        return cls.database


class _DependencyOverrides:
    """Temporarily override module-level dependencies for deterministic testing."""

    def __init__(
        self,
        *,
        weighting_policy: _WeightingPolicyStub,
        retry_policy: _RetryPolicyStub,
        database: _DatabaseStub,
    ) -> None:
        self._weighting_policy = weighting_policy
        self._retry_policy = retry_policy
        self._database = database
        self._original_spanner_client: Any = None
        self._original_get_retry_policy: Callable[[], object] | None = None
        self._original_weighting_policy: object | None = None

    def __enter__(self) -> None:
        """Apply dependency overrides."""
        self._original_spanner_client = memory_api.SpannerClient
        self._original_get_retry_policy = memory_api.get_retry_policy
        self._original_weighting_policy = memory_api.settings.governance.weighting

        _SpannerClientStub.database = self._database
        memory_api.SpannerClient = _SpannerClientStub
        memory_api.get_retry_policy = lambda: self._retry_policy
        memory_api.settings.governance.weighting = self._weighting_policy

    def __exit__(
        self,
        _: type[BaseException] | None,
        __: BaseException | None,
        ___: TracebackType | None,
    ) -> bool:
        """Restore original dependencies."""
        memory_api.SpannerClient = self._original_spanner_client
        if self._original_get_retry_policy is not None:
            memory_api.get_retry_policy = self._original_get_retry_policy
        if self._original_weighting_policy is not None:
            memory_api.settings.governance.weighting = self._original_weighting_policy
        return False


class TestWeightUpdateResilience:
    """Integration tests for weight update retry behavior."""

    async def test_weight_update_executes_with_batch(self) -> None:
        """Verify weight update executes batch operations."""
        batch = _BatchStub()
        database = _DatabaseStub(batch)
        with _DependencyOverrides(
            weighting_policy=_WeightingPolicyStub(enabled=True, should_trigger_result=True),
            retry_policy=_RetryPolicyStub(max_attempts=1),
            database=database,
        ):
            await MemoryAPI._update_weight_on_successful_use(
                TENANT_ID,
                TEST_NODE_IDS,
                session_action_count=5,
            )

        assert batch.execute_update_calls == 1

    async def test_weight_update_disabled_skips_execution(self) -> None:
        """Verify weight update skips when disabled."""
        batch = _BatchStub()
        database = _DatabaseStub(batch)
        with _DependencyOverrides(
            weighting_policy=_WeightingPolicyStub(enabled=False),
            retry_policy=_RetryPolicyStub(max_attempts=1),
            database=database,
        ):
            await MemoryAPI._update_weight_on_successful_use(
                TENANT_ID,
                TEST_NODE_IDS,
                session_action_count=5,
            )

        assert batch.execute_update_calls == 0

    async def test_weight_update_below_trigger_threshold_skips(self) -> None:
        """Verify weight update skips when should_trigger returns False."""
        batch = _BatchStub()
        database = _DatabaseStub(batch)
        with _DependencyOverrides(
            weighting_policy=_WeightingPolicyStub(enabled=True, should_trigger_result=False),
            retry_policy=_RetryPolicyStub(max_attempts=1),
            database=database,
        ):
            await MemoryAPI._update_weight_on_successful_use(
                TENANT_ID,
                TEST_NODE_IDS,
                session_action_count=5,
            )

        assert batch.execute_update_calls == 0

    async def test_weight_update_with_multiple_node_ids(self) -> None:
        """Verify weight update processes multiple node IDs in batch."""
        batch = _BatchStub()
        database = _DatabaseStub(batch)
        with _DependencyOverrides(
            weighting_policy=_WeightingPolicyStub(enabled=True, should_trigger_result=True),
            retry_policy=_RetryPolicyStub(max_attempts=1),
            database=database,
        ):
            node_ids = ["node_1", "node_2", "node_3", "node_4", "node_5"]
            await MemoryAPI._update_weight_on_successful_use(
                TENANT_ID,
                node_ids,
                session_action_count=10,
            )

        assert batch.execute_update_calls == 1
