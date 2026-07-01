"""Unit tests for retry logic."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.client.retry import RetryConfig, async_retry_with_backoff

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_DELAY_SEC = 30.0
DEFAULT_EXPONENTIAL_BASE = 2.0
SECOND_DELAY = 2.0
THIRD_DELAY = 4.0
MAX_DELAY_CAP = 5.0
RETRY_EXHAUSTED_ATTEMPTS = 2
RETRY_CALLBACK_INVOCATIONS = 2


class TestRetryConfig:
    """Test retry configuration."""

    def test_default_config(self) -> None:
        """Default retry config values."""
        config = RetryConfig()
        assert config.max_attempts == DEFAULT_MAX_ATTEMPTS
        assert config.base_delay_sec == 1.0
        assert config.max_delay_sec == DEFAULT_MAX_DELAY_SEC
        assert config.exponential_base == DEFAULT_EXPONENTIAL_BASE

    def test_calculate_delay_exponential(self) -> None:
        """Delay calculation with exponential backoff."""
        config = RetryConfig(base_delay_sec=1.0, exponential_base=DEFAULT_EXPONENTIAL_BASE)
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == SECOND_DELAY
        assert config.calculate_delay(2) == THIRD_DELAY

    def test_calculate_delay_respects_max(self) -> None:
        """Delay is capped at max_delay_sec."""
        config = RetryConfig(
            base_delay_sec=1.0,
            exponential_base=DEFAULT_EXPONENTIAL_BASE,
            max_delay_sec=MAX_DELAY_CAP,
        )
        assert config.calculate_delay(10) == MAX_DELAY_CAP


class TestAsyncRetry:
    """Test async retry with backoff."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self) -> None:
        """Success on first attempt."""
        async_func = AsyncMock(return_value="success")
        result = await async_retry_with_backoff(async_func)
        assert result == "success"
        assert async_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_success(self) -> None:
        """Retry on failure, then succeed."""
        async_func = AsyncMock(side_effect=[ValueError("fail 1"), ValueError("fail 2"), "success"])
        result = await async_retry_with_backoff(
            async_func,
            config=RetryConfig(max_attempts=DEFAULT_MAX_ATTEMPTS, base_delay_sec=0.01),
        )
        assert result == "success"
        assert async_func.call_count == DEFAULT_MAX_ATTEMPTS

    @pytest.mark.asyncio
    async def test_exhausts_retries_raises_runtime_error(self) -> None:
        """Exhausted retries raise RuntimeError."""
        async_func = AsyncMock(side_effect=ValueError("always fail"))
        config = RetryConfig(max_attempts=RETRY_EXHAUSTED_ATTEMPTS, base_delay_sec=0.01)

        with pytest.raises(RuntimeError, match="All 2 retry attempts exhausted"):
            await async_retry_with_backoff(async_func, config=config)

        assert async_func.call_count == RETRY_EXHAUSTED_ATTEMPTS

    @pytest.mark.asyncio
    async def test_on_retry_callback_invoked(self) -> None:
        """on_retry callback is invoked."""
        async_func = AsyncMock(side_effect=[ValueError("fail 1"), ValueError("fail 2"), "success"])
        on_retry_calls: list[tuple[int, Exception]] = []

        def on_retry(attempt: int, exc: Exception) -> None:
            on_retry_calls.append((attempt, exc))

        config = RetryConfig(max_attempts=DEFAULT_MAX_ATTEMPTS, base_delay_sec=0.01)
        await async_retry_with_backoff(async_func, config=config, on_retry=on_retry)

        assert len(on_retry_calls) == RETRY_CALLBACK_INVOCATIONS
        assert on_retry_calls[0][0] == 1
        assert isinstance(on_retry_calls[0][1], ValueError)

    @pytest.mark.asyncio
    async def test_delay_timing(self) -> None:
        """Delays are approximately correct."""
        async_func = AsyncMock(side_effect=[ValueError("fail"), ValueError("fail"), "success"])
        config = RetryConfig(
            max_attempts=DEFAULT_MAX_ATTEMPTS,
            base_delay_sec=0.05,
            exponential_base=DEFAULT_EXPONENTIAL_BASE,
        )

        start = asyncio.get_event_loop().time()
        await async_retry_with_backoff(async_func, config=config)
        elapsed = asyncio.get_event_loop().time() - start

        # Expected: 0.05 + 0.1 = 0.15 seconds min
        assert elapsed >= 0.15 - 0.01  # Allow 10ms tolerance


class TestDbRetry:
    """Tests for src.db.retry.async_retry_with_backoff (Spanner-specific retry logic)."""

    @pytest.mark.asyncio
    async def test_async_retry_propagates_cancelled_error(self) -> None:
        """CancelledError must bypass retry logic entirely and propagate immediately."""
        from src.db.retry import async_retry_with_backoff as db_async_retry

        call_count = 0

        async def always_raises() -> None:
            nonlocal call_count
            call_count += 1
            raise asyncio.CancelledError("task cancelled")

        with pytest.raises(asyncio.CancelledError):
            await db_async_retry(always_raises, max_attempts=5, initial_backoff_seconds=0.01)

        assert call_count == 1, "CancelledError must not trigger retries"
