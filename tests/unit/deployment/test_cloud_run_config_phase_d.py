"""Tests for Cloud Run deployment configuration (Phase D).

Test Coverage:
  - CloudRunConfig initialization and validation
  - DeploymentEnvironment enum
  - CloudRunMemory and CloudRunCPU enums
  - Environment-specific factory functions
  - Deployment command generation
  - Configuration logging
"""
# ruff: noqa: PLR2004

from __future__ import annotations

import pytest

from src.deployment.cloud_run_config import (
    CloudRunConfig,
    CloudRunCPU,
    CloudRunDeploymentManager,
    CloudRunMemory,
    DeploymentEnvironment,
    create_dev_config,
    create_prod_config,
    create_staging_config,
)


class TestDeploymentEnvironment:
    """Tests for DeploymentEnvironment enum."""

    def test_deployment_environment_values(self) -> None:
        """Test deployment environment enum values."""
        assert DeploymentEnvironment.DEV.value == "dev"
        assert DeploymentEnvironment.STAGING.value == "staging"
        assert DeploymentEnvironment.PROD.value == "prod"

    def test_deployment_environment_from_string(self) -> None:
        """Test creating environment from string."""
        env = DeploymentEnvironment("dev")
        assert env == DeploymentEnvironment.DEV


class TestCloudRunMemory:
    """Tests for CloudRunMemory enum."""

    def test_memory_values(self) -> None:
        """Test memory allocation options."""
        assert CloudRunMemory.SMALL.value == "512Mi"
        assert CloudRunMemory.MEDIUM.value == "1Gi"
        assert CloudRunMemory.LARGE.value == "2Gi"
        assert CloudRunMemory.XLARGE.value == "4Gi"


class TestCloudRunCPU:
    """Tests for CloudRunCPU enum."""

    def test_cpu_values(self) -> None:
        """Test CPU allocation options."""
        assert CloudRunCPU.ONE.value == "1"
        assert CloudRunCPU.TWO.value == "2"
        assert CloudRunCPU.FOUR.value == "4"


class TestCloudRunConfig:
    """Tests for CloudRunConfig dataclass."""

    def test_basic_config_creation(self) -> None:
        """Test creating basic configuration."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
        )
        assert config.project_id == "test-project"
        assert config.region == "us-central1"
        assert config.service_name == "test-api"
        assert config.environment == DeploymentEnvironment.DEV

    def test_config_with_environment(self) -> None:
        """Test config with explicit environment."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
            environment=DeploymentEnvironment.PROD,
        )
        assert config.environment == DeploymentEnvironment.PROD

    def test_config_with_memory_cpu(self) -> None:
        """Test config with custom memory and CPU."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
            memory=CloudRunMemory.LARGE,
            cpu=CloudRunCPU.FOUR,
        )
        assert config.memory == CloudRunMemory.LARGE
        assert config.cpu == CloudRunCPU.FOUR

    def test_config_with_labels(self) -> None:
        """Test config with custom labels."""
        labels = {"team": "data", "version": "1.0"}
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
            labels=labels,
        )
        assert config.labels == labels

    def test_config_missing_project_id(self) -> None:
        """Test config validation with missing project_id."""
        with pytest.raises(ValueError, match="project_id is required"):
            CloudRunConfig(
                project_id="",
                region="us-central1",
                service_name="test-api",
                image_uri="gcr.io/test-project/image:latest",
            )

    def test_config_missing_region(self) -> None:
        """Test config validation with missing region."""
        with pytest.raises(ValueError, match="region is required"):
            CloudRunConfig(
                project_id="test-project",
                region="",
                service_name="test-api",
                image_uri="gcr.io/test-project/image:latest",
            )

    def test_config_missing_service_name(self) -> None:
        """Test config validation with missing service_name."""
        with pytest.raises(ValueError, match="service_name is required"):
            CloudRunConfig(
                project_id="test-project",
                region="us-central1",
                service_name="",
                image_uri="gcr.io/test-project/image:latest",
            )

    def test_config_missing_image_uri(self) -> None:
        """Test config validation with missing image_uri."""
        with pytest.raises(ValueError, match="image_uri is required"):
            CloudRunConfig(
                project_id="test-project",
                region="us-central1",
                service_name="test-api",
                image_uri="",
            )

    def test_config_invalid_timeout_below_min(self) -> None:
        """Test config validation with timeout below minimum."""
        with pytest.raises(ValueError, match="timeout_seconds must be between"):
            CloudRunConfig(
                project_id="test-project",
                region="us-central1",
                service_name="test-api",
                image_uri="gcr.io/test-project/image:latest",
                timeout_seconds=0,
            )

    def test_config_invalid_timeout_above_max(self) -> None:
        """Test config validation with timeout above maximum."""
        with pytest.raises(ValueError, match="timeout_seconds must be between"):
            CloudRunConfig(
                project_id="test-project",
                region="us-central1",
                service_name="test-api",
                image_uri="gcr.io/test-project/image:latest",
                timeout_seconds=3601,
            )

    def test_config_invalid_max_instances(self) -> None:
        """Test config validation with invalid max_instances."""
        with pytest.raises(ValueError, match="max_instances must be"):
            CloudRunConfig(
                project_id="test-project",
                region="us-central1",
                service_name="test-api",
                image_uri="gcr.io/test-project/image:latest",
                max_instances=0,
            )

    def test_config_invalid_min_instances(self) -> None:
        """Test config validation with invalid min_instances."""
        with pytest.raises(ValueError, match="min_instances must be"):
            CloudRunConfig(
                project_id="test-project",
                region="us-central1",
                service_name="test-api",
                image_uri="gcr.io/test-project/image:latest",
                min_instances=-1,
            )

    def test_get_environment_suffix_prod(self) -> None:
        """Test environment suffix for production."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
            environment=DeploymentEnvironment.PROD,
        )
        assert config.get_environment_suffix() == ""

    def test_get_environment_suffix_staging(self) -> None:
        """Test environment suffix for staging."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
            environment=DeploymentEnvironment.STAGING,
        )
        assert config.get_environment_suffix() == "-staging"

    def test_get_environment_suffix_dev(self) -> None:
        """Test environment suffix for development."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
            environment=DeploymentEnvironment.DEV,
        )
        assert config.get_environment_suffix() == "-dev"

    def test_get_service_name_with_env_prod(self) -> None:
        """Test service name with environment (prod)."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="extraction-api",
            image_uri="gcr.io/test-project/image:latest",
            environment=DeploymentEnvironment.PROD,
        )
        assert config.get_service_name_with_env() == "extraction-api"

    def test_get_service_name_with_env_dev(self) -> None:
        """Test service name with environment (dev)."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="extraction-api",
            image_uri="gcr.io/test-project/image:latest",
            environment=DeploymentEnvironment.DEV,
        )
        assert config.get_service_name_with_env() == "extraction-api-dev"


class TestCloudRunDeploymentManager:
    """Tests for CloudRunDeploymentManager."""

    def test_manager_initialization(self) -> None:
        """Test deployment manager initialization."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
        )
        manager = CloudRunDeploymentManager(config)
        assert manager.config == config

    def test_validate_configuration_success(self) -> None:
        """Test successful configuration validation."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
        )
        manager = CloudRunDeploymentManager(config)
        assert manager.validate_configuration() is True

    def test_validate_configuration_empty_project_id(self) -> None:
        """Test validation fails with empty project_id."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
        )
        config.project_id = ""
        manager = CloudRunDeploymentManager(config)
        with pytest.raises(ValueError, match="project_id cannot be empty"):
            manager.validate_configuration()

    def test_get_deployment_command_basic(self) -> None:
        """Test basic deployment command generation."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
        )
        manager = CloudRunDeploymentManager(config)
        command = manager.get_deployment_command()

        assert "gcloud run deploy" in command
        assert "test-api-dev" in command
        assert "gcr.io/test-project/image:latest" in command
        assert "us-central1" in command
        assert "1Gi" in command  # Default memory is MEDIUM
        assert "--cpu=2" in command  # Default CPU is TWO

    def test_get_deployment_command_with_auth(self) -> None:
        """Test deployment command with authentication required."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
            enable_authentication=True,
        )
        manager = CloudRunDeploymentManager(config)
        command = manager.get_deployment_command()

        assert "--require-authentication" in command

    def test_get_deployment_command_without_auth(self) -> None:
        """Test deployment command without authentication."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
            enable_authentication=False,
        )
        manager = CloudRunDeploymentManager(config)
        command = manager.get_deployment_command()

        assert "--allow-unauthenticated" in command

    def test_get_deployment_command_with_instances(self) -> None:
        """Test deployment command with instance limits."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
            max_instances=100,
            min_instances=2,
        )
        manager = CloudRunDeploymentManager(config)
        command = manager.get_deployment_command()

        assert "--max-instances=100" in command
        assert "--min-instances=2" in command

    def test_get_deployment_command_with_labels(self) -> None:
        """Test deployment command with labels."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
            labels={"team": "data", "version": "1.0"},
        )
        manager = CloudRunDeploymentManager(config)
        command = manager.get_deployment_command()

        assert "--labels=" in command
        assert "team=data" in command
        assert "version=1.0" in command

    def test_get_rollback_command(self) -> None:
        """Test rollback command generation."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
        )
        manager = CloudRunDeploymentManager(config)
        command = manager.get_rollback_command("revision-001")

        assert "update-traffic" in command
        assert "revision-001" in command
        assert "100" in command

    def test_get_canary_deployment_command(self) -> None:
        """Test canary deployment command generation."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
        )
        manager = CloudRunDeploymentManager(config)
        command = manager.get_canary_deployment_command(new_revision_traffic=10)

        assert "update-traffic" in command
        assert "LATEST=10" in command

    def test_canary_deployment_invalid_traffic(self) -> None:
        """Test canary deployment with invalid traffic percentage."""
        config = CloudRunConfig(
            project_id="test-project",
            region="us-central1",
            service_name="test-api",
            image_uri="gcr.io/test-project/image:latest",
        )
        manager = CloudRunDeploymentManager(config)
        with pytest.raises(ValueError, match="new_revision_traffic must be between"):
            manager.get_canary_deployment_command(new_revision_traffic=101)


class TestFactoryFunctions:
    """Tests for environment-specific factory functions."""

    def test_create_prod_config(self) -> None:
        """Test production config factory."""
        config = create_prod_config(
            project_id="prod-project",
            image_uri="gcr.io/prod-project/image:latest",
        )
        assert config.project_id == "prod-project"
        assert config.environment == DeploymentEnvironment.PROD
        assert config.memory == CloudRunMemory.LARGE
        assert config.cpu == CloudRunCPU.TWO
        assert config.enable_authentication is True
        assert config.min_instances == 2

    def test_create_staging_config(self) -> None:
        """Test staging config factory."""
        config = create_staging_config(
            project_id="staging-project",
            image_uri="gcr.io/staging-project/image:latest",
        )
        assert config.project_id == "staging-project"
        assert config.environment == DeploymentEnvironment.STAGING
        assert config.memory == CloudRunMemory.MEDIUM
        assert config.cpu == CloudRunCPU.TWO

    def test_create_dev_config(self) -> None:
        """Test development config factory."""
        config = create_dev_config(
            project_id="dev-project",
            image_uri="gcr.io/dev-project/image:latest",
        )
        assert config.project_id == "dev-project"
        assert config.environment == DeploymentEnvironment.DEV
        assert config.memory == CloudRunMemory.SMALL
        assert config.cpu == CloudRunCPU.ONE
        assert config.enable_authentication is False

    def test_prod_config_with_labels(self) -> None:
        """Test production config with custom labels."""
        labels = {"team": "platform", "costcenter": "engineering"}
        config = create_prod_config(
            project_id="prod-project",
            image_uri="gcr.io/prod-project/image:latest",
            labels=labels,
        )
        assert config.labels == labels
