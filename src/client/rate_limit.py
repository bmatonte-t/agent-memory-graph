"""Rate limiting for client requests."""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Deque

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(
        self,
        rate_limit: int = 100,
        window_sec: int = 60,
        burst_capacity: int | None = None,
    ) -> None:
        """Initialize rate limiter.

        Args:
            rate_limit: Allowed requests per window.
            window_sec: Time window in seconds.
            burst_capacity: Burst capacity; defaults to rate_limit.
        """
        self.rate_limit = rate_limit
        self.window_sec = window_sec
        self.burst_capacity = burst_capacity or rate_limit
        self.tokens: float = float(self.burst_capacity)
        self.last_refill = time.time()
        self.request_times: Deque[float] = deque(maxlen=rate_limit)

    def is_allowed(self) -> bool:
        """Check if a request is allowed under rate limit.

        Returns:
            True if request is allowed, False otherwise.
        """
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            self.request_times.append(time.time())
            return True
        return False

    def wait_if_needed(self) -> float:
        """Block until a request token is available.

        Returns:
            Seconds waited.
        """
        start = time.time()
        while not self.is_allowed():
            time.sleep(0.01)  # Poll every 10ms
        return time.time() - start

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        refill_rate = self.rate_limit / self.window_sec
        tokens_to_add = elapsed * refill_rate
        self.tokens = min(self.tokens + tokens_to_add, float(self.burst_capacity))
        self.last_refill = now

    def remaining(self) -> int:
        """Return approximate remaining tokens."""
        self._refill()
        return int(self.tokens)
