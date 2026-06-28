"""Cloud Scheduler job configuration and management.

This module sets up Cloud Scheduler jobs to automate BigQuery ingestion:
  - Creates scheduled jobs for per-table ingestion
  - Manages Cloud Run job payloads
  - Supports daily/hourly/custom schedules
  - Handles job lifecycle (create, update, delete, pause)

All jobs are configured with Pub/Sub message delivery and retry policies.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from google.cloud import scheduler_v1

from src.integrations.google_sdk_wrappers import as_scheduler_client

if TYPE_CHECKING:
    from collections.abc import Iterable

    from src.integrations.google_sdk_wrappers import (
        SchedulerClientProtocol,
        SchedulerJobData,
    )

logger = logging.getLogger(__name__)

# Default retry and execution settings
DEFAULT_RETRY_COUNT = 5
DEFAULT_RETRY_BACKOFF = 5  # seconds
DEFAULT_RETRY_MAX_BACKOFF = 3600  # 1 hour
DEFAULT_EXECUTION_TIMEOUT = 3600  # 1 hour


class CloudSchedulerJobConfig:
    """Configuration for a Cloud Scheduler job.

    Attributes:
        job_name: Full job resource name (projects/X/locations/Y/jobs/Z).
        table_id: BigQuery table to ingest.
        schedule: Cron expression for job frequency.
        timezone: Timezone for cron schedule (default: UTC).
        description: Human-readable job description.
        paused: Whether the job is initially paused.
    """

    def __init__(
        self,
        job_name: str,
        table_id: str,
        schedule: str,
        *,
        timezone: str = "UTC",
        description: str = "",
        paused: bool = False,
    ) -> None:
        """Initialize CloudSchedulerJobConfig.

        Args:
            job_name: Full job resource name.
            table_id: BigQuery table identifier.
            schedule: Cron expression (e.g., "0 2 * * *" for daily 2 AM).
            timezone: Timezone for schedule interpretation.
            description: Optional job description.
            paused: If True, job starts in paused state.

        Raises:
            ValueError: If job_name or table_id is empty.
        """
        if not job_name or not job_name.strip():
            msg = "job_name cannot be empty"
            raise ValueError(msg)
        if not table_id or not table_id.strip():
            msg = "table_id cannot be empty"
            raise ValueError(msg)

        self.job_name = job_name
        self.table_id = table_id
        self.schedule = schedule
        self.timezone = timezone
        self.description = description or f"Ingest {table_id}"
        self.paused = paused


class CloudSchedulerError(Exception):
    """Cloud Scheduler operation error.

    Attributes:
        error_code: Machine-readable error code.
        error_message: Human-readable error description.
        job_name: Name of the job involved (if applicable).
        project_id: GCP project ID.
    """

    def __init__(
        self,
        error_code: str,
        error_message: str,
        job_name: str = "",
        project_id: str = "",
    ) -> None:
        """Initialize CloudSchedulerError.

        Args:
            error_code: Error code identifier.
            error_message: Descriptive error message.
            job_name: Related job name.
            project_id: Related project ID.
        """
        self.error_code = error_code
        self.error_message = error_message
        self.job_name = job_name
        self.project_id = project_id
        msg = f"[{error_code}] {error_message}"
        if job_name:
            msg += f" (job: {job_name})"
        super().__init__(msg)


class CloudSchedulerManager:
    """Manage Cloud Scheduler jobs for BigQuery ingestion orchestration.

    Handles job creation, updates, deletion, and lifecycle management
    with proper error handling and logging.
    """

    def __init__(
        self,
        project_id: str,
        region: str,
        topic_name: str,
        client: scheduler_v1.CloudSchedulerClient | None = None,
    ) -> None:
        """Initialize CloudSchedulerManager.

        Args:
            project_id: GCP project ID.
            region: Cloud Scheduler region (e.g., "us-central1").
            topic_name: Pub/Sub topic for job payloads.
            client: Optional pre-configured scheduler client.

        Raises:
            ValueError: If project_id, region, or topic_name is empty.
        """
        if not project_id or not project_id.strip():
            msg = "project_id cannot be empty"
            raise ValueError(msg)
        if not region or not region.strip():
            msg = "region cannot be empty"
            raise ValueError(msg)
        if not topic_name or not topic_name.strip():
            msg = "topic_name cannot be empty"
            raise ValueError(msg)

        self.project_id = project_id
        self.region = region
        self.topic_name = topic_name
        # Keep reference to SDK client for methods not in protocol
        self._sdk_client = client or scheduler_v1.CloudSchedulerClient()
        # Cast to typed protocol at the boundary
        self.client: SchedulerClientProtocol = as_scheduler_client(self._sdk_client)
        self.parent_path = self._sdk_client.common_location_path(project_id, region)

        logger.debug(
            "Initialized CloudSchedulerManager (project=%s, region=%s)",
            project_id,
            region,
        )

    def create_job(
        self,
        config: CloudSchedulerJobConfig,
        table_id: str,
        bigquery_dataset_id: str,
        spanner_project_id: str,
        spanner_instance_id: str,
        spanner_database_id: str,
        tenant_id: str,
        cloud_run_service_url: str,
    ) -> str:
        """Create a Cloud Scheduler job for table ingestion.

        Constructs a Cloud Run job payload with all required ingestion
        parameters and creates a scheduled job in Cloud Scheduler.

        Args:
            config: CloudSchedulerJobConfig with schedule and metadata.
            table_id: BigQuery table to ingest.
            bigquery_dataset_id: BigQuery dataset identifier.
            spanner_project_id: Spanner project ID.
            spanner_instance_id: Spanner instance ID.
            spanner_database_id: Spanner database ID.
            tenant_id: Tenant identifier for isolation.
            cloud_run_service_url: Cloud Run service URL endpoint.

        Returns:
            str: Full job resource name.

        Raises:
            CloudSchedulerError: If job creation fails.
        """
        try:
            # Build Pub/Sub payload for ingestion job
            payload = {
                "table_id": table_id,
                "bigquery_dataset_id": bigquery_dataset_id,
                "spanner_project_id": spanner_project_id,
                "spanner_instance_id": spanner_instance_id,
                "spanner_database_id": spanner_database_id,
                "tenant_id": tenant_id,
                "cloud_run_service_url": cloud_run_service_url,
                "created_at": datetime.now(UTC).isoformat(),
            }

            # Build job request
            job = {
                "name": config.job_name,
                "description": config.description,
                "schedule": config.schedule,
                "time_zone": config.timezone,
                "pubsub_target": {
                    "topic_name": self.topic_name,
                    "data": json.dumps(payload).encode("utf-8"),
                },
                "retry_config": {
                    "retry_count": DEFAULT_RETRY_COUNT,
                    "max_backoff_duration": {
                        "seconds": DEFAULT_RETRY_MAX_BACKOFF,
                    },
                    "min_backoff_duration": {
                        "seconds": DEFAULT_RETRY_BACKOFF,
                    },
                },
                "attempt_deadline": {
                    "seconds": DEFAULT_EXECUTION_TIMEOUT,
                },
            }

            # Create the job
            created_job = self.client.create_job(
                request={
                    "parent": self.parent_path,
                    "job": job,
                }
            )
            created_job_data = cast("SchedulerJobData", created_job)

            logger.info(
                "Created Cloud Scheduler job: %s (table=%s, schedule=%s)",
                created_job_data.name,
                table_id,
                config.schedule,
            )

            return created_job_data.name  # noqa: TRY300

        except Exception as e:
            msg = f"Failed to create scheduler job for {table_id}: {e!s}"
            logger.exception(msg)
            raise CloudSchedulerError(
                error_code="JOB_CREATION_FAILED",
                error_message=msg,
                job_name=config.job_name,
                project_id=self.project_id,
            ) from e

    def delete_job(self, job_name: str) -> None:
        """Delete a Cloud Scheduler job.

        Args:
            job_name: Full job resource name to delete.

        Raises:
            CloudSchedulerError: If deletion fails.
        """
        try:
            self.client.delete_job(request={"name": job_name})
            logger.info("Deleted Cloud Scheduler job: %s", job_name)

        except Exception as e:
            msg = f"Failed to delete scheduler job {job_name}: {e!s}"
            logger.exception(msg)
            raise CloudSchedulerError(
                error_code="JOB_DELETION_FAILED",
                error_message=msg,
                job_name=job_name,
                project_id=self.project_id,
            ) from e

    def pause_job(self, job_name: str) -> None:
        """Pause a Cloud Scheduler job.

        Paused jobs do not execute until resumed.

        Args:
            job_name: Full job resource name to pause.

        Raises:
            CloudSchedulerError: If pause operation fails.
        """
        try:
            self.client.pause_job(request={"name": job_name})
            logger.info("Paused Cloud Scheduler job: %s", job_name)

        except Exception as e:
            msg = f"Failed to pause scheduler job {job_name}: {e!s}"
            logger.exception(msg)
            raise CloudSchedulerError(
                error_code="JOB_PAUSE_FAILED",
                error_message=msg,
                job_name=job_name,
                project_id=self.project_id,
            ) from e

    def resume_job(self, job_name: str) -> None:
        """Resume a paused Cloud Scheduler job.

        Args:
            job_name: Full job resource name to resume.

        Raises:
            CloudSchedulerError: If resume operation fails.
        """
        try:
            self.client.resume_job(request={"name": job_name})
            logger.info("Resumed Cloud Scheduler job: %s", job_name)

        except Exception as e:
            msg = f"Failed to resume scheduler job {job_name}: {e!s}"
            logger.exception(msg)
            raise CloudSchedulerError(
                error_code="JOB_RESUME_FAILED",
                error_message=msg,
                job_name=job_name,
                project_id=self.project_id,
            ) from e

    def get_job(self, job_name: str) -> scheduler_v1.Job:
        """Retrieve a Cloud Scheduler job by name.

        Args:
            job_name: Full job resource name.

        Returns:
            scheduler_v1.Job: Job details and current state.

        Raises:
            CloudSchedulerError: If retrieval fails.
        """
        try:
            job = self.client.get_job(request={"name": job_name})
            logger.debug("Retrieved Cloud Scheduler job: %s", job_name)
            return cast("scheduler_v1.Job", job)

        except Exception as e:
            msg = f"Failed to retrieve scheduler job {job_name}: {e!s}"
            logger.exception(msg)
            raise CloudSchedulerError(
                error_code="JOB_RETRIEVAL_FAILED",
                error_message=msg,
                job_name=job_name,
                project_id=self.project_id,
            ) from e

    def list_jobs(self) -> list[scheduler_v1.Job]:
        """List all Cloud Scheduler jobs in the region.

        Returns:
            list[scheduler_v1.Job]: All jobs in the configured region.

        Raises:
            CloudSchedulerError: If listing fails.
        """
        try:
            request = {"parent": self.parent_path}
            jobs_iter = cast("Iterable[scheduler_v1.Job]", self.client.list_jobs(request=request))
            jobs = list(jobs_iter)
            logger.debug("Listed %d Cloud Scheduler jobs", len(jobs))
            return jobs  # noqa: TRY300

        except Exception as e:
            msg = f"Failed to list scheduler jobs: {e!s}"
            logger.exception(msg)
            raise CloudSchedulerError(
                error_code="JOB_LIST_FAILED",
                error_message=msg,
                project_id=self.project_id,
            ) from e

    def build_job_name(self, table_id: str) -> str:
        """Build a Cloud Scheduler job name from table ID.

        Converts table names to valid Cloud Scheduler job names
        (lowercase, hyphens instead of underscores).

        Args:
            table_id: BigQuery table identifier.

        Returns:
            str: Full job resource name for the table.
        """
        # Replace underscores with hyphens and lowercase
        job_id = table_id.replace("_", "-").lower()
        return self._sdk_client.job_path(self.project_id, self.region, job_id)
