"""Idempotency key management for resilient write operations."""

from __future__ import annotations

import contextvars
import logging
import uuid
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)

# Context variable for storing the current idempotency key
_current_idempotency_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "idempotency_key", default=None
)


def generate_idempotency_key() -> str:
    """Generate a unique idempotency key for an operation.

    Returns:
        str: UUID-based idempotency key.
    """
    return str(uuid.uuid4())


def set_idempotency_key(key: str) -> contextvars.Token[str | None]:
    """Set the idempotency key for the current operation context.

    Args:
        key: Idempotency key to set.

    Returns:
        contextvars.Token: Context token for resetting the key later.
    """
    logger.debug("idempotency_key_set key=%s", key[:8])
    return _current_idempotency_key.set(key)


def get_idempotency_key() -> str | None:
    """Get the current idempotency key from context.

    Returns:
        str | None: The idempotency key, or None if not set.
    """
    return _current_idempotency_key.get()


def reset_idempotency_key(token: contextvars.Token[str | None]) -> None:
    """Reset the idempotency key using a previously returned token.

    Args:
        token: Context token returned from set_idempotency_key().
    """
    key = _current_idempotency_key.get()
    _current_idempotency_key.reset(token)
    logger.debug("idempotency_key_reset key=%s", key[:8] if key else None)


class IdempotencyContext:
    """Context manager for scoped idempotency key handling.

    Usage:
        with IdempotencyContext() as ctx:
            # Within this block, an idempotency key is set and available
            key = ctx.key
            # Perform operations that can be safely retried
    """

    def __init__(self, key: str | None = None) -> None:
        """Initialize IdempotencyContext.

        Args:
            key: Optional idempotency key. If not provided, a new one is generated.
        """
        self.key = key or generate_idempotency_key()
        self._token: contextvars.Token[str | None] | None = None

    def __enter__(self) -> Self:
        """Enter the context and set the idempotency key.

        Returns:
            Self: Self for 'with' statement binding.
        """
        self._token = set_idempotency_key(self.key)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context and reset the idempotency key.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        if self._token is not None:
            reset_idempotency_key(self._token)
