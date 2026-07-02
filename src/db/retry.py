"""Retry logic with exponential backoff for resilient Spanner operations."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

from google.api_core import exceptions as gcp_exceptions

from src.project_base.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Spanner error codes (from google.api_core.gapic_v1.code_pb2)
RETRYABLE_ERROR_CODES = {
    "ABORTED": 10,  # Transaction conflict
    "RESOURCE_EXHAUSTED": 8,  # Database busy
    "DEADLINE_EXCEEDED": 4,  # Timeout (may be transient)
}


def is_transient_error(exception: Exception) -> bool:
    """Determine if an error is transient and safe to retry.

    Args:
        exception: The exception to classify.

    Returns:
        bool: True if the error is transient (retryable), False otherwise.
    """
    if not isinstance(exception, gcp_exceptions.GoogleAPICallError):
        return False

    # Get error code safely - exception.code is a grpc.StatusCode enum
    error_code: str | None = None
    try:
        if hasattr(exception, "code") and exception.code is not None:
            error_code_name = str(exception.code).split(".")[-1]
            error_code = error_code_name
    except AttributeError, IndexError, TypeError:
        pass

    # Check if it's a known transient error code
    if error_code is not None and error_code in RETRYABLE_ERROR_CODES:
        return True

    # Handle INTERNAL errors that mention timeout/deadline
    if error_code == "INTERNAL":
        error_message = str(exception).lower()
        return "deadline" in error_message or "timeout" in error_message

    return False


def calculate_backoff(
    attempt: int,
    *,
    initial_backoff_seconds: float = 0.25,
    max_backoff_seconds: float = 5.0,
) -> float:
    """Calculate exponential backoff with jitter.

    Args:
        attempt: Zero-indexed attempt number (0, 1, 2, ...).
        initial_backoff_seconds: Initial backoff duration.
        max_backoff_seconds: Maximum backoff duration.

    Returns:
        float: Backoff duration in seconds.
    """
    base_backoff = initial_backoff_seconds * (2**attempt)
    jitter = random.uniform(0, 1)  # noqa: S311 - jitter does not require cryptographic randomness
    return min(base_backoff + jitter, max_backoff_seconds)


async def async_retry_with_backoff(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    initial_backoff_seconds: float = 0.25,
    max_backoff_seconds: float = 5.0,
    **kwargs: Any,
) -> Any:
    """Execute async function with exponential backoff retry on transient errors.

    Args:
        func: Async function to execute.
        *args: Positional arguments to pass to func.
        max_attempts: Maximum number of attempts (must be >= 1).
        initial_backoff_seconds: Initial backoff duration.
        max_backoff_seconds: Maximum backoff duration.
        **kwargs: Keyword arguments to pass to func.

    Returns:
        Any: Return value from func.

    Raises:
        Exception: The last exception if all retries are exhausted.
    """
    if max_attempts < 1:
        msg = "max_attempts must be >= 1"
        raise ValueError(msg)

    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except asyncio.CancelledError:
            raise  # Always re-raise immediately — never retry cancelled tasks
        except Exception as e:
            last_error = e
            is_retryable = is_transient_error(e)

            if not is_retryable or attempt == max_attempts - 1:
                logger.exception(
                    ("operation_failed tenant_id=%s attempt=%d max_attempts=%d is_retryable=%s"),
                    kwargs.get("tenant_id", "unknown"),
                    attempt + 1,
                    max_attempts,
                    is_retryable,
                )
                raise

            # Calculate backoff and wait
            backoff_seconds = calculate_backoff(
                attempt,
                initial_backoff_seconds=initial_backoff_seconds,
                max_backoff_seconds=max_backoff_seconds,
            )

            logger.info(
                (
                    "write_retry_attempt tenant_id=%s attempt=%d max_attempts=%d "
                    "backoff_seconds=%.3f error=%s"
                ),
                kwargs.get("tenant_id", "unknown"),
                attempt + 1,
                max_attempts,
                backoff_seconds,
                str(e),
            )

            await asyncio.sleep(backoff_seconds)

    # This should not be reached, but handle it just in case
    if last_error:
        raise last_error

    msg = "Unexpected: no error and max attempts exceeded"
    raise RuntimeError(msg)


def get_retry_policy() -> Any:
    """Get the configured retry policy from settings.

    Returns:
        RetryPolicy: Configured retry policy with max_attempts and backoff params.
    """
    return settings.governance.retry
