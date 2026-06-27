"""Unit tests for Cloud Scheduler job management.

Tests cover job creation, deletion, lifecycle management, and error handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.cloud import scheduler_v1

from src.pipelines.bigquery_ingestion.cloud_scheduler_setup import (
    CloudSchedulerError,
    CloudSchedulerJobConfig,
    CloudSchedulerManager,
)

# Test constants
PROJECT_ID = "test-project"
REGION = "us-central1"
TOPIC_NAME = "projects/test-project/topics/ingestion-jobs"
TABLE_ID = "my_table"
BIGQUERY_DATASET_ID = "bq_dataset"
SPANNER_PROJECT_ID = "spanner-project"
SPANNER_INSTANCE_ID = "spanner-instance"
SPANNER_DATABASE_ID = "spanner-database"
TENANT_ID = "tenant-1"
CLOUD_RUN_URL = "https://ingest.example.com"
SCHEDULE_DAILY = "0 2 * * *"  # 2 AM UTC daily
SCHEDULE_HOURLY = "0 * * * *"  # Every hour
TIMEZONE_UTC = "UTC"
TIMEZONE_EST = "America/New_York"
JOB_NAME = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/my-table"
VALID_RETRY_COUNT = 5
VALID_TIMEOUT = 3600
EXPECTED_JOBS_COUNT = 2


class TestCloudSchedulerJobConfig:
    """Tests for CloudSchedulerJobConfig."""

    def test_config_initialization(self) -> None:
        """Test successful config initialization."""
        config = CloudSchedulerJobConfig(
            job_name=JOB_NAME,
            table_id=TABLE_ID,
            schedule=SCHEDULE_DAILY,
            timezone=TIMEZONE_UTC,
        )

        assert config.job_name == JOB_NAME
        assert config.table_id == TABLE_ID
        assert config.schedule == SCHEDULE_DAILY
        assert config.timezone == TIMEZONE_UTC
        assert config.paused is False

    def test_config_with_description(self) -> None:
        """Test config with custom description."""
        custom_desc = "Custom ingestion job"
        config = CloudSchedulerJobConfig(
            job_name=JOB_NAME,
            table_id=TABLE_ID,
            schedule=SCHEDULE_DAILY,
            description=custom_desc,
        )

        assert config.description == custom_desc

    def test_config_with_paused_flag(self) -> None:
        """Test config initialized as paused."""
        config = CloudSchedulerJobConfig(
            job_name=JOB_NAME,
            table_id=TABLE_ID,
            schedule=SCHEDULE_DAILY,
            paused=True,
        )

        assert config.paused is True

    def test_config_validation_empty_job_name(self) -> None:
        """Test that empty job_name raises ValueError."""
        with pytest.raises(ValueError, match=r"job_name cannot be empty"):
            CloudSchedulerJobConfig(
                job_name="",
                table_id=TABLE_ID,
                schedule=SCHEDULE_DAILY,
            )

    def test_config_validation_empty_table_id(self) -> None:
        """Test that empty table_id raises ValueError."""
        with pytest.raises(ValueError, match=r"table_id cannot be empty"):
            CloudSchedulerJobConfig(
                job_name=JOB_NAME,
                table_id="",
                schedule=SCHEDULE_DAILY,
            )

    def test_config_default_description(self) -> None:
        """Test that description defaults to table-based message."""
        config = CloudSchedulerJobConfig(
            job_name=JOB_NAME,
            table_id=TABLE_ID,
            schedule=SCHEDULE_DAILY,
        )

        assert f"Ingest {TABLE_ID}" in config.description


class TestCloudSchedulerError:
    """Tests for CloudSchedulerError exception."""

    def test_error_initialization(self) -> None:
        """Test error initialization with all fields."""
        error = CloudSchedulerError(
            error_code="TEST_ERROR",
            error_message="Test message",
            job_name=JOB_NAME,
            project_id=PROJECT_ID,
        )

        assert error.error_code == "TEST_ERROR"
        assert error.error_message == "Test message"
        assert error.job_name == JOB_NAME
        assert error.project_id == PROJECT_ID
        assert "[TEST_ERROR]" in str(error)

    def test_error_message_formatting(self) -> None:
        """Test error message includes job context."""
        error = CloudSchedulerError(
            error_code="JOB_CREATION_FAILED",
            error_message="Failed to create",
            job_name=JOB_NAME,
        )

        assert JOB_NAME in str(error)


class TestCloudSchedulerManager:
    """Tests for CloudSchedulerManager."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock scheduler client."""
        return MagicMock(spec=scheduler_v1.CloudSchedulerClient)

    @pytest.fixture
    def manager(self, mock_client: MagicMock) -> CloudSchedulerManager:
        """Create a CloudSchedulerManager with mocked client."""
        manager = CloudSchedulerManager(
            project_id=PROJECT_ID,
            region=REGION,
            topic_name=TOPIC_NAME,
            client=mock_client,
        )
        # Mock common_location_path
        manager.client.common_location_path.return_value = (
            f"projects/{PROJECT_ID}/locations/{REGION}"
        )
        manager.client.job_path.return_value = JOB_NAME
        return manager

    def test_manager_initialization(self, mock_client: MagicMock) -> None:
        """Test manager initialization with valid parameters."""
        manager = CloudSchedulerManager(
            project_id=PROJECT_ID,
            region=REGION,
            topic_name=TOPIC_NAME,
            client=mock_client,
        )

        assert manager.project_id == PROJECT_ID
        assert manager.region == REGION
        assert manager.topic_name == TOPIC_NAME
        assert manager.client is mock_client

    def test_manager_validation_empty_project_id(self, mock_client: MagicMock) -> None:
        """Test that empty project_id raises ValueError."""
        with pytest.raises(ValueError, match=r"project_id cannot be empty"):
            CloudSchedulerManager(
                project_id="",
                region=REGION,
                topic_name=TOPIC_NAME,
                client=mock_client,
            )

    def test_manager_validation_empty_region(self, mock_client: MagicMock) -> None:
        """Test that empty region raises ValueError."""
        with pytest.raises(ValueError, match=r"region cannot be empty"):
            CloudSchedulerManager(
                project_id=PROJECT_ID,
                region="",
                topic_name=TOPIC_NAME,
                client=mock_client,
            )

    def test_manager_validation_empty_topic(self, mock_client: MagicMock) -> None:
        """Test that empty topic_name raises ValueError."""
        with pytest.raises(ValueError, match=r"topic_name cannot be empty"):
            CloudSchedulerManager(
                project_id=PROJECT_ID,
                region=REGION,
                topic_name="",
                client=mock_client,
            )

    def test_create_job_success(self, manager: CloudSchedulerManager) -> None:
        """Test successful job creation."""
        config = CloudSchedulerJobConfig(
            job_name=JOB_NAME,
            table_id=TABLE_ID,
            schedule=SCHEDULE_DAILY,
        )
        mock_job = MagicMock()
        mock_job.name = JOB_NAME
        manager.client.create_job.return_value = mock_job

        result = manager.create_job(
            config=config,
            table_id=TABLE_ID,
            bigquery_dataset_id=BIGQUERY_DATASET_ID,
            spanner_project_id=SPANNER_PROJECT_ID,
            spanner_instance_id=SPANNER_INSTANCE_ID,
            spanner_database_id=SPANNER_DATABASE_ID,
            tenant_id=TENANT_ID,
            cloud_run_service_url=CLOUD_RUN_URL,
        )

        assert result == JOB_NAME
        manager.client.create_job.assert_called_once()

    def test_create_job_error_handling(self, manager: CloudSchedulerManager) -> None:
        """Test error handling during job creation."""
        config = CloudSchedulerJobConfig(
            job_name=JOB_NAME,
            table_id=TABLE_ID,
            schedule=SCHEDULE_DAILY,
        )
        manager.client.create_job.side_effect = RuntimeError("API error")

        with pytest.raises(
            CloudSchedulerError,
            match="JOB_CREATION_FAILED",
        ):
            manager.create_job(
                config=config,
                table_id=TABLE_ID,
                bigquery_dataset_id=BIGQUERY_DATASET_ID,
                spanner_project_id=SPANNER_PROJECT_ID,
                spanner_instance_id=SPANNER_INSTANCE_ID,
                spanner_database_id=SPANNER_DATABASE_ID,
                tenant_id=TENANT_ID,
                cloud_run_service_url=CLOUD_RUN_URL,
            )

    def test_delete_job_success(self, manager: CloudSchedulerManager) -> None:
        """Test successful job deletion."""
        manager.client.delete_job.return_value = None

        manager.delete_job(JOB_NAME)

        manager.client.delete_job.assert_called_once_with(request={"name": JOB_NAME})

    def test_delete_job_error_handling(self, manager: CloudSchedulerManager) -> None:
        """Test error handling during job deletion."""
        manager.client.delete_job.side_effect = RuntimeError("Deletion failed")

        with pytest.raises(
            CloudSchedulerError,
            match="JOB_DELETION_FAILED",
        ):
            manager.delete_job(JOB_NAME)

    def test_pause_job_success(self, manager: CloudSchedulerManager) -> None:
        """Test successful job pause."""
        manager.client.pause_job.return_value = None

        manager.pause_job(JOB_NAME)

        manager.client.pause_job.assert_called_once_with(request={"name": JOB_NAME})

    def test_pause_job_error_handling(self, manager: CloudSchedulerManager) -> None:
        """Test error handling during job pause."""
        manager.client.pause_job.side_effect = RuntimeError("Pause failed")

        with pytest.raises(
            CloudSchedulerError,
            match="JOB_PAUSE_FAILED",
        ):
            manager.pause_job(JOB_NAME)

    def test_resume_job_success(self, manager: CloudSchedulerManager) -> None:
        """Test successful job resume."""
        manager.client.resume_job.return_value = None

        manager.resume_job(JOB_NAME)

        manager.client.resume_job.assert_called_once_with(request={"name": JOB_NAME})

    def test_resume_job_error_handling(self, manager: CloudSchedulerManager) -> None:
        """Test error handling during job resume."""
        manager.client.resume_job.side_effect = RuntimeError("Resume failed")

        with pytest.raises(
            CloudSchedulerError,
            match="JOB_RESUME_FAILED",
        ):
            manager.resume_job(JOB_NAME)

    def test_get_job_success(self, manager: CloudSchedulerManager) -> None:
        """Test successful job retrieval."""
        mock_job = MagicMock(spec=scheduler_v1.Job)
        mock_job.name = JOB_NAME
        manager.client.get_job.return_value = mock_job

        result = manager.get_job(JOB_NAME)

        assert result.name == JOB_NAME
        manager.client.get_job.assert_called_once_with(request={"name": JOB_NAME})

    def test_get_job_error_handling(self, manager: CloudSchedulerManager) -> None:
        """Test error handling during job retrieval."""
        manager.client.get_job.side_effect = RuntimeError("Get failed")

        with pytest.raises(
            CloudSchedulerError,
            match="JOB_RETRIEVAL_FAILED",
        ):
            manager.get_job(JOB_NAME)

    def test_list_jobs_success(self, manager: CloudSchedulerManager) -> None:
        """Test successful job listing."""
        mock_job1 = MagicMock(spec=scheduler_v1.Job)
        mock_job1.name = "job1"
        mock_job2 = MagicMock(spec=scheduler_v1.Job)
        mock_job2.name = "job2"
        manager.client.list_jobs.return_value = [mock_job1, mock_job2]

        result = manager.list_jobs()

        assert len(result) == EXPECTED_JOBS_COUNT
        assert result[0].name == "job1"
        assert result[1].name == "job2"

    def test_list_jobs_error_handling(self, manager: CloudSchedulerManager) -> None:
        """Test error handling during job listing."""
        manager.client.list_jobs.side_effect = RuntimeError("List failed")

        with pytest.raises(
            CloudSchedulerError,
            match="JOB_LIST_FAILED",
        ):
            manager.list_jobs()

    def test_build_job_name(self, manager: CloudSchedulerManager) -> None:
        """Test job name builder converts table ID properly."""
        manager.client.job_path.return_value = JOB_NAME

        result = manager.build_job_name(TABLE_ID)

        manager.client.job_path.assert_called_once_with(
            PROJECT_ID,
            REGION,
            TABLE_ID.replace("_", "-").lower(),
        )
        assert result == JOB_NAME

    def test_build_job_name_special_chars(self, manager: CloudSchedulerManager) -> None:
        """Test job name builder with special characters."""
        table_with_underscore = "my_long_table_name"
        manager.client.job_path.return_value = (
            f"projects/{PROJECT_ID}/locations/{REGION}/jobs/my-long-table-name"
        )

        manager.build_job_name(table_with_underscore)

        # Verify that job_path was called with hyphens instead of underscores
        call_args = manager.client.job_path.call_args[0]
        assert call_args[2] == "my-long-table-name"
