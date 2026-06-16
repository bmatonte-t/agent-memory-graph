"""Cognitive weighting and temporal decay module."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from src.db.schema import SchemaConfig
from src.db.spanner_client import SpannerClient

logger = logging.getLogger(__name__)


class CognitiveWeighting:
    """Manages cognitive weight updates, decay, and scheduling."""

    @staticmethod
    async def decay_weights_temporal(decay_rate: float = SchemaConfig.TEMPORAL_DECAY_RATE) -> int:
        """
        Decay all node weights by temporal distance.

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
            raise ValueError("decay_rate must be between 0.0 and 1.0")

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
            database = SpannerClient.get_database()
            with database.batch() as batch:
                batch.execute_update(
                    sql,
                    {
                        "decay_rate": decay_rate,
                        "tier_semantic": SchemaConfig.MEMORY_TIER_SEMANTIC,
                        "tier_context": SchemaConfig.MEMORY_TIER_CONTEXT,
                    },
                )

            logger.info(f"Applied temporal decay with rate={decay_rate}")
            return 0  # Spanner batch doesn't return row count, return 0
        except Exception as e:
            raise RuntimeError(f"Failed to decay weights: {e}")

    @staticmethod
    async def prune_weights_below_threshold(
        threshold: float = SchemaConfig.WEIGHT_THRESHOLD,
    ) -> int:
        """
        Soft-delete nodes whose weight falls below cognitive threshold.

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
            raise ValueError("threshold must be between 0.0 and 1.0")

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
            database = SpannerClient.get_database()
            with database.batch() as batch:
                batch.execute_update(
                    sql,
                    {
                        "threshold": threshold,
                        "tier_semantic": SchemaConfig.MEMORY_TIER_SEMANTIC,
                        "tier_context": SchemaConfig.MEMORY_TIER_CONTEXT,
                    },
                )

            logger.info(f"Pruned nodes below threshold={threshold}")
            return 0
        except Exception as e:
            raise RuntimeError(f"Failed to prune weights: {e}")

    @staticmethod
    async def get_weight_statistics() -> dict:
        """
        Retrieve aggregate weight statistics for monitoring.

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
            stats = {}

            with database.snapshot() as snapshot:
                results = snapshot.execute_sql(
                    sql,
                    {
                        "tier_context": SchemaConfig.MEMORY_TIER_CONTEXT,
                        "tier_semantic": SchemaConfig.MEMORY_TIER_SEMANTIC,
                        "tier_audit": SchemaConfig.MEMORY_TIER_AUDIT,
                    },
                )

                for row in results:
                    tier, count, mean, min_w, max_w, median = row
                    stats[tier] = {
                        "count": count,
                        "mean_weight": mean or 0.0,
                        "min_weight": min_w or 0.0,
                        "max_weight": max_w or 0.0,
                        "median_weight": median or 0.0,
                    }

            return stats
        except Exception as e:
            raise RuntimeError(f"Failed to get weight statistics: {e}")


class CloudSchedulerJob:
    """Manages Cloud Scheduler integration for periodic decay."""

    DECAY_SCHEDULE_CRON = "0 2 * * *"  # Run daily at 2 AM UTC
    PRUNING_SCHEDULE_CRON = "0 3 * * *"  # Run daily at 3 AM UTC

    @staticmethod
    async def create_decay_job(project_id: str, location: str = "us-central1") -> dict:
        """
        Create a Cloud Scheduler job for nightly weight decay.

        Args:
            project_id: GCP project ID
            location: Cloud Scheduler location (default: us-central1)

        Returns:
            Dict with job configuration details

        Raises:
            RuntimeError: If job creation fails
        """
        try:
            from google.cloud import scheduler_v1
            from google.cloud.scheduler_v1.types import HttpTarget, Job

            client = scheduler_v1.CloudSchedulerClient()
            parent = client.common_location_path(project_id, location)

            job = Job(
                name=f"{parent}/jobs/amg-decay-weights-daily",
                description="Daily cognitive weight decay for agent memory graph",
                schedule=CloudSchedulerJob.DECAY_SCHEDULE_CRON,
                time_zone="UTC",
                http_target=HttpTarget(
                    uri="https://{cloud_run_url}/internal/decay-weights",
                    http_method="POST",
                    headers={"Content-Type": "application/json"},
                    body=b'{"decay_rate": 0.05}',
                ),
                attempt_config={
                    "max_retries": 2,
                    "max_backoff_duration": {"seconds": 3600},
                    "min_backoff_duration": {"seconds": 60},
                },
            )

            response = client.create_job(
                request={"parent": parent, "job": job}
            )
            logger.info(f"Created Cloud Scheduler job: {response.name}")
            return {
                "name": response.name,
                "schedule": CloudSchedulerJob.DECAY_SCHEDULE_CRON,
                "status": "created",
            }
        except ImportError:
            raise RuntimeError(
                "google-cloud-scheduler not installed. Install with: "
                "pip install google-cloud-scheduler"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create Cloud Scheduler job: {e}")

    @staticmethod
    async def create_pruning_job(project_id: str, location: str = "us-central1") -> dict:
        """
        Create a Cloud Scheduler job for weight-based pruning.

        Args:
            project_id: GCP project ID
            location: Cloud Scheduler location

        Returns:
            Dict with job configuration

        Raises:
            RuntimeError: If job creation fails
        """
        try:
            from google.cloud import scheduler_v1
            from google.cloud.scheduler_v1.types import HttpTarget, Job

            client = scheduler_v1.CloudSchedulerClient()
            parent = client.common_location_path(project_id, location)

            job = Job(
                name=f"{parent}/jobs/amg-prune-weights-daily",
                description="Daily cognitive weight pruning for agent memory graph",
                schedule=CloudSchedulerJob.PRUNING_SCHEDULE_CRON,
                time_zone="UTC",
                http_target=HttpTarget(
                    uri="https://{cloud_run_url}/internal/prune-weights",
                    http_method="POST",
                    headers={"Content-Type": "application/json"},
                    body=b'{"threshold": 0.30}',
                ),
                attempt_config={
                    "max_retries": 2,
                    "max_backoff_duration": {"seconds": 3600},
                    "min_backoff_duration": {"seconds": 60},
                },
            )

            response = client.create_job(
                request={"parent": parent, "job": job}
            )
            logger.info(f"Created Cloud Scheduler job: {response.name}")
            return {
                "name": response.name,
                "schedule": CloudSchedulerJob.PRUNING_SCHEDULE_CRON,
                "status": "created",
            }
        except ImportError:
            raise RuntimeError(
                "google-cloud-scheduler not installed. Install with: "
                "pip install google-cloud-scheduler"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create pruning job: {e}")

    @staticmethod
    def get_job_config() -> dict:
        """Return Cloud Scheduler job configuration for Terraform/deployment."""
        return {
            "decay_job": {
                "name": "amg-decay-weights-daily",
                "schedule": CloudSchedulerJob.DECAY_SCHEDULE_CRON,
                "timezone": "UTC",
                "http_target": {
                    "uri": "{cloud_run_url}/internal/decay-weights",
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
                    "uri": "{cloud_run_url}/internal/prune-weights",
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
