"""Unit tests for rate limiting."""

from __future__ import annotations

import time

import pytest

from src.client.rate_limit import RateLimiter


class TestRateLimiter:
    """Test rate limiting."""

    def test_init_burst_capacity_defaults_to_rate_limit(self) -> None:
        """Burst capacity defaults to rate_limit."""
        limiter = RateLimiter(rate_limit=50)
        assert limiter.burst_capacity == 50

    def test_init_custom_burst_capacity(self) -> None:
        """Custom burst capacity."""
        limiter = RateLimiter(rate_limit=50, burst_capacity=100)
        assert limiter.burst_capacity == 100

    def test_is_allowed_grants_token_on_available(self) -> None:
        """is_allowed() grants token when available."""
        limiter = RateLimiter(rate_limit=10, burst_capacity=10)
        initial_tokens = limiter.tokens
        assert limiter.is_allowed() is True
        assert limiter.tokens == initial_tokens - 1.0  # Token consumed

    def test_is_allowed_denies_when_exhausted(self) -> None:
        """is_allowed() denies when tokens exhausted."""
        limiter = RateLimiter(rate_limit=2)
        assert limiter.is_allowed() is True
        assert limiter.is_allowed() is True
        assert limiter.is_allowed() is False

    def test_refill_over_time(self) -> None:
        """Tokens refill over time."""
        limiter = RateLimiter(rate_limit=60, window_sec=1, burst_capacity=1)  # 1 token per second, capacity 1
        assert limiter.is_allowed() is True  # Consume initial token
        assert limiter.tokens < 1.0

        # Wait 1.2 seconds for refill
        time.sleep(1.2)

        # Approximately 1 token should be available
        assert limiter.is_allowed() is True

    def test_remaining(self) -> None:
        """remaining() returns approximate token count."""
        limiter = RateLimiter(rate_limit=100, burst_capacity=100)
        remaining = limiter.remaining()
        assert remaining == 100

        limiter.is_allowed()
        remaining = limiter.remaining()
        assert remaining == 99

    def test_wait_if_needed_blocks_until_available(self) -> None:
        """wait_if_needed() blocks until token available."""
        limiter = RateLimiter(rate_limit=2, window_sec=1)
        limiter.is_allowed()
        limiter.is_allowed()
        assert limiter.is_allowed() is False

        start = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start

        # Should wait ~0.5 seconds for one token to refill
        assert elapsed >= 0.4
