"""Tests for cognitive weighting and temporal decay."""

from unittest.mock import MagicMock, patch

import pytest

from src.memory.cognitive_weighting import CloudSchedulerJob, CognitiveWeighting

EXPECTED_CONTEXT_COUNT = 10
EXPECTED_CONTEXT_MEAN_WEIGHT = 0.55
EXPECTED_SEMANTIC_COUNT = 50


class TestTemporalDecay:
    """Tests for temporal weight decay."""

    @pytest.mark.asyncio
    async def test_decay_weights_temporal_success(self) -> None:
        """Test successful temporal decay execution."""
        with patch("src.memory.cognitive_weighting.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            result = await CognitiveWeighting.decay_weights_temporal()

            assert result == 0
            mock_batch.execute_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_decay_weights_with_custom_rate(self) -> None:
        """Test decay with custom decay rate."""
        with patch("src.memory.cognitive_weighting.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            custom_rate = 0.10
            await CognitiveWeighting.decay_weights_temporal(decay_rate=custom_rate)

            # Verify custom rate was passed
            call_args = mock_batch.execute_update.call_args
            params = call_args[0][1]
            assert params["decay_rate"] == custom_rate

    @pytest.mark.asyncio
    async def test_decay_weights_invalid_rate_too_low(self) -> None:
        """Test decay with invalid rate (below 0.0)."""
        with pytest.raises(ValueError, match=r"decay_rate must be between 0.0 and 1.0"):
            await CognitiveWeighting.decay_weights_temporal(decay_rate=-0.1)

    @pytest.mark.asyncio
    async def test_decay_weights_invalid_rate_too_high(self) -> None:
        """Test decay with invalid rate (above 1.0)."""
        with pytest.raises(ValueError, match=r"decay_rate must be between 0.0 and 1.0"):
            await CognitiveWeighting.decay_weights_temporal(decay_rate=1.5)

    @pytest.mark.asyncio
    async def test_decay_weights_zero_rate(self) -> None:
        """Test decay with zero rate (no decay)."""
        with patch("src.memory.cognitive_weighting.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            await CognitiveWeighting.decay_weights_temporal(decay_rate=0.0)
            mock_batch.execute_update.assert_called_once()


    @pytest.mark.asyncio
    async def test_decay_weights_temporal_returns_actual_affected_count(self) -> None:
        """Returns count of affected nodes, not hardcoded 0, via pre-DML COUNT query."""
        with patch("src.memory.cognitive_weighting.SpannerClient") as mock_client:
            mock_db = MagicMock()
            # Snapshot returns 7 rows affected
            mock_snapshot = MagicMock()
            mock_snapshot.execute_sql.return_value = iter([[7]])
            mock_db.snapshot.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.snapshot.return_value.__exit__ = MagicMock(return_value=None)
            # Batch for DML
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            count = await CognitiveWeighting.decay_weights_temporal()

            assert count == 7, f"Expected 7 affected nodes, got {count}"

    @pytest.mark.asyncio
    async def test_decay_weights_temporal_returns_zero_when_no_nodes_match(self) -> None:
        """Returns 0 when no nodes qualify for temporal decay."""
        with patch("src.memory.cognitive_weighting.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_snapshot = MagicMock()
            mock_snapshot.execute_sql.return_value = iter([[0]])
            mock_db.snapshot.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.snapshot.return_value.__exit__ = MagicMock(return_value=None)
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            count = await CognitiveWeighting.decay_weights_temporal()

            assert count == 0


class TestWeightPruning:
    """Tests for weight-based pruning."""

    @pytest.mark.asyncio
    async def test_prune_weights_below_threshold_success(self) -> None:
        """Test successful weight pruning."""
        with patch("src.memory.cognitive_weighting.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            result = await CognitiveWeighting.prune_weights_below_threshold()

            assert result == 0
            mock_batch.execute_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_prune_weights_custom_threshold(self) -> None:
        """Test pruning with custom threshold."""
        with patch("src.memory.cognitive_weighting.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_batch = MagicMock()
            mock_db.batch.return_value.__enter__ = MagicMock(return_value=mock_batch)
            mock_db.batch.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            custom_threshold = 0.20
            await CognitiveWeighting.prune_weights_below_threshold(threshold=custom_threshold)

            call_args = mock_batch.execute_update.call_args
            params = call_args[0][1]
            assert params["threshold"] == custom_threshold

    @pytest.mark.asyncio
    async def test_prune_weights_invalid_threshold_low(self) -> None:
        """Test pruning with invalid threshold (below 0.0)."""
        with pytest.raises(ValueError, match=r"threshold must be between 0.0 and 1.0"):
            await CognitiveWeighting.prune_weights_below_threshold(threshold=-0.1)

    @pytest.mark.asyncio
    async def test_prune_weights_invalid_threshold_high(self) -> None:
        """Test pruning with invalid threshold (above 1.0)."""
        with pytest.raises(ValueError, match=r"threshold must be between 0.0 and 1.0"):
            await CognitiveWeighting.prune_weights_below_threshold(threshold=1.5)


class TestWeightStatistics:
    """Tests for weight statistics aggregation."""

    @pytest.mark.asyncio
    async def test_get_weight_statistics_success(self) -> None:
        """Test retrieving weight statistics."""
        with patch("src.memory.cognitive_weighting.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_snapshot = MagicMock()
            mock_snapshot.execute_sql.return_value = [
                ("CONTEXT", 10, 0.55, 0.30, 0.80, 0.55),
                ("SEMANTIC", 50, 0.52, 0.25, 0.75, 0.50),
                ("AUDIT", 100, 0.50, 0.50, 0.50, 0.50),
            ]
            mock_db.snapshot.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.snapshot.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            stats = await CognitiveWeighting.get_weight_statistics()

            assert "CONTEXT" in stats
            assert "SEMANTIC" in stats
            assert "AUDIT" in stats
            assert stats["CONTEXT"]["count"] == EXPECTED_CONTEXT_COUNT
            assert stats["CONTEXT"]["mean_weight"] == EXPECTED_CONTEXT_MEAN_WEIGHT
            assert stats["SEMANTIC"]["count"] == EXPECTED_SEMANTIC_COUNT

    @pytest.mark.asyncio
    async def test_get_weight_statistics_empty_results(self) -> None:
        """Test statistics with no data."""
        with patch("src.memory.cognitive_weighting.SpannerClient") as mock_client:
            mock_db = MagicMock()
            mock_snapshot = MagicMock()
            mock_snapshot.execute_sql.return_value = []
            mock_db.snapshot.return_value.__enter__ = MagicMock(return_value=mock_snapshot)
            mock_db.snapshot.return_value.__exit__ = MagicMock(return_value=None)

            mock_client.get_database.return_value = mock_db

            stats = await CognitiveWeighting.get_weight_statistics()

            assert stats == {}


class TestCloudSchedulerJob:
    """Tests for Cloud Scheduler job management."""

    def test_get_job_config(self) -> None:
        """Test Cloud Scheduler job configuration generation."""
        config = CloudSchedulerJob.get_job_config("https://example.run.app")

        assert "decay_job" in config
        assert "pruning_job" in config
        assert config["decay_job"]["schedule"] == CloudSchedulerJob.DECAY_SCHEDULE_CRON
        assert config["pruning_job"]["schedule"] == CloudSchedulerJob.PRUNING_SCHEDULE_CRON
        assert (
            config["decay_job"]["http_target"]["uri"]
            == "https://example.run.app/internal/decay-weights"
        )
        assert (
            config["pruning_job"]["http_target"]["uri"]
            == "https://example.run.app/internal/prune-weights"
        )

    def test_decay_schedule_cron_format(self) -> None:
        """Test decay job CRON schedule format."""
        # Should be daily at 2 AM UTC: "0 2 * * *"
        assert CloudSchedulerJob.DECAY_SCHEDULE_CRON == "0 2 * * *"

    def test_pruning_schedule_cron_format(self) -> None:
        """Test pruning job CRON schedule format."""
        # Should be daily at 3 AM UTC: "0 3 * * *"
        assert CloudSchedulerJob.PRUNING_SCHEDULE_CRON == "0 3 * * *"

    @pytest.mark.asyncio
    async def test_create_decay_job_not_installed(self) -> None:
        """Test decay job creation fails gracefully when scheduler not installed."""
        # This test verifies the ImportError handling
        with (
            patch.dict("sys.modules", {"google.cloud.scheduler_v1": None}),
            patch("builtins.__import__", side_effect=ImportError("No module")),
            pytest.raises(RuntimeError, match="google-cloud-scheduler not installed"),
        ):
            await CloudSchedulerJob.create_decay_job(
                project_id="test-project",
                cloud_run_url="https://example.run.app",
            )

    @pytest.mark.asyncio
    async def test_create_pruning_job_not_installed(self) -> None:
        """Test pruning job creation fails gracefully when scheduler not installed."""
        with (
            patch.dict("sys.modules", {"google.cloud.scheduler_v1": None}),
            patch("builtins.__import__", side_effect=ImportError("No module")),
            pytest.raises(RuntimeError, match="google-cloud-scheduler not installed"),
        ):
            await CloudSchedulerJob.create_pruning_job(
                project_id="test-project",
                cloud_run_url="https://example.run.app",
            )

    def test_job_config_has_required_fields(self) -> None:
        """Test that job config contains all required fields."""
        config = CloudSchedulerJob.get_job_config("example.run.app")

        for job_name in ["decay_job", "pruning_job"]:
            job = config[job_name]
            assert "name" in job
            assert "schedule" in job
            assert "timezone" in job
            assert "http_target" in job
            assert "uri" in job["http_target"]
            assert "http_method" in job["http_target"]
            assert job["http_target"]["http_method"] == "POST"

    def test_build_target_uri_rejects_empty_url(self) -> None:
        """Target URI builder should reject empty Cloud Run URLs."""
        with pytest.raises(ValueError, match="cloud_run_url cannot be empty"):
            CloudSchedulerJob._build_target_uri("", "/internal/decay-weights")
