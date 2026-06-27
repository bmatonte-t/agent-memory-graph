"""Retry logic with exponential backoff."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import TypeVar, overload

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay_sec: float = 1.0,
        max_delay_sec: float = 30.0,
        exponential_base: float = 2.0,
        retryable_status_codes: set[int] | None = None,
    ) -> None:
        """Initialize retry config.

        Args:
            max_attempts: Maximum number of retry attempts.
            base_delay_sec: Initial delay in seconds.
            max_delay_sec: Maximum delay between retries.
            exponential_base: Base for exponential backoff calculation.
            retryable_status_codes: HTTP status codes to retry on (503, 504 by default).
        """
        self.max_attempts = max_attempts
        self.base_delay_sec = base_delay_sec
        self.max_delay_sec = max_delay_sec
        self.exponential_base = exponential_base
        self.retryable_status_codes = retryable_status_codes or {503, 504}

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.

        Args:
            attempt: Attempt number (0-indexed).

        Returns:
            Delay in seconds, capped at max_delay_sec.
        """
        delay = self.base_delay_sec * (self.exponential_base ** attempt)
        return min(delay, self.max_delay_sec)


async def async_retry_with_backoff(
    func: Callable[[], Coroutine[None, None, T]],
    config: RetryConfig | None = None,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    """Execute async function with exponential backoff retry.

    Args:
        func: Async callable to execute.
        config: Retry configuration.
        on_retry: Optional callback invoked on each retry (attempt, exception).

    Returns:
        Result of func() on success.

    Raises:
        The last exception encountered if all retries exhausted.
    """
    config = config or RetryConfig()
    last_exception: Exception | None = None

    for attempt in range(config.max_attempts):
        try:
            return await func()
        except Exception as e:  # noqa: BLE001
            last_exception = e
            if attempt < config.max_attempts - 1:
                delay = config.calculate_delay(attempt)
                if on_retry:
                    on_retry(attempt + 1, e)
                logger.debug(
                    "Retry attempt %d after delay %.1fs: %s",
                    attempt + 1,
                    delay,
                    type(e).__name__,
                )
                await asyncio.sleep(delay)

    msg = f"All {config.max_attempts} retry attempts exhausted"
    raise RuntimeError(msg) from last_exception
