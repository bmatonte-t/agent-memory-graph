"""Unit tests for retry logic."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.client.retry import RetryConfig, async_retry_with_backoff


class TestRetryConfig:
    """Test retry configuration."""

    def test_default_config(self) -> None:
        """Default retry config values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay_sec == 1.0
        assert config.max_delay_sec == 30.0
        assert config.exponential_base == 2.0

    def test_calculate_delay_exponential(self) -> None:
        """Delay calculation with exponential backoff."""
        config = RetryConfig(base_delay_sec=1.0, exponential_base=2.0)
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0

    def test_calculate_delay_respects_max(self) -> None:
        """Delay is capped at max_delay_sec."""
        config = RetryConfig(
            base_delay_sec=1.0, exponential_base=2.0, max_delay_sec=5.0
        )
        assert config.calculate_delay(10) == 5.0


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
        async_func = AsyncMock(
            side_effect=[ValueError("fail 1"), ValueError("fail 2"), "success"]
        )
        result = await async_retry_with_backoff(
            async_func,
            config=RetryConfig(max_attempts=3, base_delay_sec=0.01),
        )
        assert result == "success"
        assert async_func.call_count == 3

    @pytest.mark.asyncio
    async def test_exhausts_retries_raises_runtime_error(self) -> None:
        """Exhausted retries raise RuntimeError."""
        async_func = AsyncMock(side_effect=ValueError("always fail"))
        config = RetryConfig(max_attempts=2, base_delay_sec=0.01)

        with pytest.raises(RuntimeError, match="All 2 retry attempts exhausted"):
            await async_retry_with_backoff(async_func, config=config)

        assert async_func.call_count == 2

    @pytest.mark.asyncio
    async def test_on_retry_callback_invoked(self) -> None:
        """on_retry callback is invoked."""
        async_func = AsyncMock(
            side_effect=[ValueError("fail 1"), ValueError("fail 2"), "success"]
        )
        on_retry_calls: list[tuple[int, Exception]] = []

        def on_retry(attempt: int, exc: Exception) -> None:
            on_retry_calls.append((attempt, exc))

        config = RetryConfig(max_attempts=3, base_delay_sec=0.01)
        await async_retry_with_backoff(async_func, config=config, on_retry=on_retry)

        assert len(on_retry_calls) == 2
        assert on_retry_calls[0][0] == 1
        assert isinstance(on_retry_calls[0][1], ValueError)

    @pytest.mark.asyncio
    async def test_delay_timing(self) -> None:
        """Delays are approximately correct."""
        async_func = AsyncMock(
            side_effect=[ValueError("fail"), ValueError("fail"), "success"]
        )
        config = RetryConfig(max_attempts=3, base_delay_sec=0.05, exponential_base=2.0)

        start = asyncio.get_event_loop().time()
        await async_retry_with_backoff(async_func, config=config)
        elapsed = asyncio.get_event_loop().time() - start

        # Expected: 0.05 + 0.1 = 0.15 seconds min
        assert elapsed >= 0.15 - 0.01  # Allow 10ms tolerance
