"""Exceptions for memory operations."""

from __future__ import annotations


class MemoryOperationError(Exception):
    """Base exception for memory operation failures."""


class WeightUpdateFailedError(MemoryOperationError):
    """Weight update operation exhausted retries and failed.

    This exception indicates that a weight update operation could not be completed
    after the configured number of retry attempts.
    """

    def __init__(
        self,
        *,
        tenant_id: str,
        node_ids: list[str],
        attempts: int,
        last_error: Exception,
    ) -> None:
        """Initialize WeightUpdateFailedError exception.

        Args:
            tenant_id: Tenant identifier for the operation.
            node_ids: List of node IDs that were being updated.
            attempts: Number of attempted retries.
            last_error: The last exception that was encountered.
        """
        self.tenant_id = tenant_id
        self.node_ids = node_ids
        self.attempts = attempts
        self.last_error = last_error

        msg = (
            f"Weight update failed after {attempts} attempts "
            f"for tenant_id={tenant_id} nodes={len(node_ids)}: {last_error}"
        )
        super().__init__(msg)
