"""Cognitive weighting and temporal decay module."""

import logging

from src.db.schema import SchemaConfig
from src.db.spanner_client import SpannerClient
from src.integrations.google_sdk_wrappers import create_cloud_scheduler_http_job, execute_sql_rows

logger = logging.getLogger(__name__)


class CognitiveWeighting:
    """Manages cognitive weight updates, decay, and scheduling."""

    @staticmethod
    async def decay_weights_temporal(decay_rate: float = SchemaConfig.TEMPORAL_DECAY_RATE) -> int:
        """Decay all node weights by temporal distance.

        Implements exponential decay: weight_t = weight_0 * e^(-decay_rate * hours_since_access)

        Args:
            decay_rate: Decay rate per hour (default: 0.05 from SchemaConfig)

        Returns:
            Number of nodes updated

        Raises:
            ValueError: If decay_rate is invalid
            RuntimeError: If database update fails
        """
        if not (0.0 <= decay_rate <= 1.0):
            msg = "decay_rate must be between 0.0 and 1.0"
            raise ValueError(msg)

        # GQL/SQL to calculate hours since last access and apply decay
        # Only applies to SEMANTIC and CONTEXT tiers (AUDIT is immutable)
        sql = """
            UPDATE MemoryNode
            SET LogOddsWeight = LogOddsWeight * EXP(-@decay_rate *
                CAST(TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), LastAccessed, HOUR) AS FLOAT64)),
                UpdatedAt = CURRENT_TIMESTAMP()
            WHERE MemoryTier IN (@tier_semantic, @tier_context)
              AND LastAccessed < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
        """

        try:
            database = SpannerClient.get_database()  # type: ignore[return-value]
            with database.batch() as batch:  # type: ignore[union-attr]
                batch.execute_update(  # type: ignore[union-attr]
                    sql,
                    {
                        "decay_rate": decay_rate,
                        "tier_semantic": SchemaConfig.MEMORY_TIER_SEMANTIC,
                        "tier_context": SchemaConfig.MEMORY_TIER_CONTEXT,
                    },
                )
        except Exception as e:
            msg = f"Failed to decay weights: {e}"
            raise RuntimeError(msg) from e
        else:
            logger.info(f"Applied temporal decay with rate={decay_rate}")
            return 0  # Spanner batch doesn't return row count, return 0

    @staticmethod
    async def prune_weights_below_threshold(
        threshold: float = SchemaConfig.WEIGHT_THRESHOLD,
    ) -> int:
        """Soft-delete nodes whose weight falls below cognitive threshold.

        Marks nodes with is_deleted=true without hard deletion (audit trail preservation).

        Args:
            threshold: Minimum cognitive weight (default: 0.30)

        Returns:
            Number of nodes pruned

        Raises:
            ValueError: If threshold is invalid
            RuntimeError: If update fails
        """
        if not (0.0 <= threshold <= 1.0):
            msg = "threshold must be between 0.0 and 1.0"
            raise ValueError(msg)

        # Add a soft-delete marker without removing the node (audit preservation)
        # This requires an additional column: is_deleted BOOL
        sql = """
            UPDATE MemoryNode
            SET Attributes = JSON_SET(Attributes, '$.is_deleted', true),
                UpdatedAt = CURRENT_TIMESTAMP()
            WHERE MemoryTier IN (@tier_semantic, @tier_context)
              AND LogOddsWeight < @threshold
              AND CAST(JSON_EXTRACT_SCALAR(Attributes, '$.is_deleted') AS BOOL) != true
        """

        try:
            database = SpannerClient.get_database()  # type: ignore[return-value]
            with database.batch() as batch:  # type: ignore[union-attr]
                batch.execute_update(  # type: ignore[union-attr]
                    sql,
                    {
                        "threshold": threshold,
                        "tier_semantic": SchemaConfig.MEMORY_TIER_SEMANTIC,
                        "tier_context": SchemaConfig.MEMORY_TIER_CONTEXT,
                    },
                )
        except Exception as e:
            msg = f"Failed to prune weights: {e}"
            raise RuntimeError(msg) from e
        else:
            logger.info(f"Pruned nodes below threshold={threshold}")
            return 0

    @staticmethod
    async def get_weight_statistics() -> dict[str, dict[str, float]]:
        """Retrieve aggregate weight statistics for monitoring.

        Returns:
            Dict with mean, median, min, max weight per memory tier

        Raises:
            RuntimeError: If query fails
        """
        sql = """
            SELECT
                MemoryTier,
                COUNT(*) as count,
                AVG(LogOddsWeight) as mean_weight,
                MIN(LogOddsWeight) as min_weight,
                MAX(LogOddsWeight) as max_weight,
                APPROX_QUANTILES(LogOddsWeight, 100)[OFFSET(50)] as median_weight
            FROM MemoryNode
            WHERE MemoryTier IN (@tier_context, @tier_semantic, @tier_audit)
            GROUP BY MemoryTier
        """

        try:
            database = SpannerClient.get_database()
            stats: dict[str, dict[str, float]] = {}
            results = execute_sql_rows(
                database,
                sql,
                {
                    "tier_context": SchemaConfig.MEMORY_TIER_CONTEXT,
                    "tier_semantic": SchemaConfig.MEMORY_TIER_SEMANTIC,
                    "tier_audit": SchemaConfig.MEMORY_TIER_AUDIT,
                },
            )

            for row in results:
                tier, count, mean, min_w, max_w, median = row
                tier_key = str(tier)
                stats[tier_key] = {
                    "count": float(count) if isinstance(count, (int, float)) else 0.0,
                    "mean_weight": float(mean) if isinstance(mean, (int, float)) else 0.0,
                    "min_weight": float(min_w) if isinstance(min_w, (int, float)) else 0.0,
                    "max_weight": float(max_w) if isinstance(max_w, (int, float)) else 0.0,
                    "median_weight": float(median) if isinstance(median, (int, float)) else 0.0,
                }

        except Exception as e:
            msg = f"Failed to get weight statistics: {e}"
            raise RuntimeError(msg) from e
        else:
            return stats


class CloudSchedulerJob:
    """Manages Cloud Scheduler integration for periodic decay."""

    DECAY_SCHEDULE_CRON = "0 2 * * *"  # Run daily at 2 AM UTC
    PRUNING_SCHEDULE_CRON = "0 3 * * *"  # Run daily at 3 AM UTC

    @staticmethod
    def _build_target_uri(cloud_run_url: str, path: str) -> str:
        """Build a valid Cloud Run target URI for scheduler jobs.

        Args:
            cloud_run_url: Base Cloud Run service URL.
            path: Internal endpoint path.

        Returns:
            str: Fully-qualified target URI.

        Raises:
            ValueError: If the URL is missing or invalid.
        """
        base_url = cloud_run_url.strip()
        if not base_url:
            msg = "cloud_run_url cannot be empty"
            raise ValueError(msg)

        if not base_url.startswith(("https://", "http://")):
            base_url = f"https://{base_url}"

        return f"{base_url.rstrip('/')}{path}"

    @staticmethod
    async def create_decay_job(
        project_id: str,
        location: str = "us-central1",
        cloud_run_url: str = "",
    ) -> dict[str, object]:
        """Create a Cloud Scheduler job for nightly weight decay.

        Args:
            project_id: GCP project ID
            location: Cloud Scheduler location (default: us-central1)
            cloud_run_url: Base URL for the Cloud Run service.

        Returns:
            Dict with job configuration details

        Raises:
            RuntimeError: If job creation fails
        """
        try:
            decay_uri = CloudSchedulerJob._build_target_uri(
                cloud_run_url=cloud_run_url,
                path="/internal/decay-weights",
            )
            response = create_cloud_scheduler_http_job(
                project_id=project_id,
                location=location,
                job_name="amg-decay-weights-daily",
                description="Daily cognitive weight decay for agent memory graph",
                schedule=CloudSchedulerJob.DECAY_SCHEDULE_CRON,
                target_uri=decay_uri,
                body_json=b'{"decay_rate": 0.05}',
            )
        except Exception as e:
            msg = f"Failed to create Cloud Scheduler job: {e}"
            raise RuntimeError(msg) from e
        else:
            logger.info(f"Created Cloud Scheduler job: {response.name}")
            return {
                "name": response.name,
                "schedule": CloudSchedulerJob.DECAY_SCHEDULE_CRON,
                "status": "created",
            }

    @staticmethod
    async def create_pruning_job(
        project_id: str,
        location: str = "us-central1",
        cloud_run_url: str = "",
    ) -> dict[str, object]:
        """Create a Cloud Scheduler job for weight-based pruning.

        Args:
            project_id: GCP project ID
            location: Cloud Scheduler location
            cloud_run_url: Base URL for the Cloud Run service.

        Returns:
            Dict with job configuration

        Raises:
            RuntimeError: If job creation fails
        """
        try:
            pruning_uri = CloudSchedulerJob._build_target_uri(
                cloud_run_url=cloud_run_url,
                path="/internal/prune-weights",
            )
            response = create_cloud_scheduler_http_job(
                project_id=project_id,
                location=location,
                job_name="amg-prune-weights-daily",
                description="Daily cognitive weight pruning for agent memory graph",
                schedule=CloudSchedulerJob.PRUNING_SCHEDULE_CRON,
                target_uri=pruning_uri,
                body_json=b'{"threshold": 0.30}',
            )
        except Exception as e:
            msg = f"Failed to create pruning job: {e}"
            raise RuntimeError(msg) from e
        else:
            logger.info(f"Created Cloud Scheduler job: {response.name}")
            return {
                "name": response.name,
                "schedule": CloudSchedulerJob.PRUNING_SCHEDULE_CRON,
                "status": "created",
            }

    @staticmethod
    def get_job_config(cloud_run_url: str) -> dict[str, object]:
        """Return Cloud Scheduler job configuration for Terraform/deployment.

        Args:
            cloud_run_url: Base URL for the Cloud Run service.

        Returns:
            dict: Scheduler job configuration payload.
        """
        decay_uri = CloudSchedulerJob._build_target_uri(
            cloud_run_url=cloud_run_url,
            path="/internal/decay-weights",
        )
        pruning_uri = CloudSchedulerJob._build_target_uri(
            cloud_run_url=cloud_run_url,
            path="/internal/prune-weights",
        )

        return {
            "decay_job": {
                "name": "amg-decay-weights-daily",
                "schedule": CloudSchedulerJob.DECAY_SCHEDULE_CRON,
                "timezone": "UTC",
                "http_target": {
                    "uri": decay_uri,
                    "http_method": "POST",
                    "headers": {"Content-Type": "application/json"},
                    "body": '{"decay_rate": 0.05}',
                },
                "retry_config": {
                    "retry_count": 2,
                    "max_backoff_duration": "3600s",
                    "min_backoff_duration": "60s",
                },
            },
            "pruning_job": {
                "name": "amg-prune-weights-daily",
                "schedule": CloudSchedulerJob.PRUNING_SCHEDULE_CRON,
                "timezone": "UTC",
                "http_target": {
                    "uri": pruning_uri,
                    "http_method": "POST",
                    "headers": {"Content-Type": "application/json"},
                    "body": '{"threshold": 0.30}',
                },
                "retry_config": {
                    "retry_count": 2,
                    "max_backoff_duration": "3600s",
                    "min_backoff_duration": "60s",
                },
            },
        }
