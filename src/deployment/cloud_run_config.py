"""Cloud Run deployment configuration and orchestration.

This module provides configuration and utilities for deploying the extraction API
to Google Cloud Run with production-grade settings, monitoring, and IAM controls.

Key Components:
  - CloudRunConfig: Configuration for Cloud Run deployment parameters
  - CloudRunDeploymentManager: Orchestrator for Cloud Run operations
  - DeploymentEnvironment: Environment-specific settings (dev/staging/prod)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

# Maximum timeout for Cloud Run requests (seconds)
MAX_TIMEOUT_SECONDS = 3600
# Minimum timeout for Cloud Run requests (seconds)
MIN_TIMEOUT_SECONDS = 1
# Maximum traffic percentage for canary deployments
MAX_TRAFFIC_PERCENTAGE = 100

logger = logging.getLogger(__name__)


class DeploymentEnvironment(StrEnum):
    """Deployment environment options.

    Attributes:
        DEV: Development environment with relaxed constraints.
        STAGING: Staging environment with production-like settings.
        PROD: Production environment with strict controls.
    """

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class CloudRunMemory(StrEnum):
    """Cloud Run memory allocation options.

    Attributes:
        SMALL: 512 MiB memory allocation.
        MEDIUM: 1 GiB memory allocation.
        LARGE: 2 GiB memory allocation.
        XLARGE: 4 GiB memory allocation.
    """

    SMALL = "512Mi"
    MEDIUM = "1Gi"
    LARGE = "2Gi"
    XLARGE = "4Gi"


class CloudRunCPU(StrEnum):
    """Cloud Run CPU allocation options.

    Attributes:
        ONE: 1 CPU core.
        TWO: 2 CPU cores.
        FOUR: 4 CPU cores.
    """

    ONE = "1"
    TWO = "2"
    FOUR = "4"


@dataclass
class CloudRunConfig:
    """Cloud Run deployment configuration.

    Attributes:
        project_id: GCP project ID for deployment.
        region: GCP region for deployment (e.g., us-central1).
        service_name: Cloud Run service name.
        image_uri: Container image URI (gcr.io/project/image:tag).
        environment: Deployment environment (dev/staging/prod).
        memory: Memory allocation (512Mi, 1Gi, 2Gi, 4Gi).
        cpu: CPU cores allocation (1, 2, 4).
        timeout_seconds: Request timeout in seconds (max 3600).
        max_instances: Maximum concurrent instances.
        min_instances: Minimum instances (for warm starts).
        enable_traffic_split: Enable traffic splitting for canary deployments.
        enable_authentication: Enable IAM authentication requirement.
        labels: Custom labels for resource tracking.
        environment_variables: Environment variables for runtime.
    """

    project_id: str
    region: str
    service_name: str
    image_uri: str
    environment: DeploymentEnvironment = DeploymentEnvironment.DEV
    memory: CloudRunMemory = CloudRunMemory.MEDIUM
    cpu: CloudRunCPU = CloudRunCPU.TWO
    timeout_seconds: int = 300
    max_instances: int | None = None
    min_instances: int | None = None
    enable_traffic_split: bool = False
    enable_authentication: bool = True
    labels: dict[str, str] = field(default_factory=dict)
    environment_variables: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate configuration after initialization.

        Raises:
            ValueError: If configuration is invalid.
        """
        if not self.project_id:
            msg = "project_id is required"
            raise ValueError(msg)
        if not self.region:
            msg = "region is required"
            raise ValueError(msg)
        if not self.service_name:
            msg = "service_name is required"
            raise ValueError(msg)
        if not self.image_uri:
            msg = "image_uri is required"
            raise ValueError(msg)
        if self.timeout_seconds < MIN_TIMEOUT_SECONDS or self.timeout_seconds > MAX_TIMEOUT_SECONDS:
            msg = f"timeout_seconds must be between {MIN_TIMEOUT_SECONDS} and {MAX_TIMEOUT_SECONDS}"
            raise ValueError(msg)
        if self.max_instances is not None and self.max_instances < 1:
            msg = "max_instances must be >= 1"
            raise ValueError(msg)
        if self.min_instances is not None and self.min_instances < 0:
            msg = "min_instances must be >= 0"
            raise ValueError(msg)

    def get_environment_suffix(self) -> str:
        """Get environment-specific suffix for service naming.

        Returns:
            str: Environment suffix (empty for prod, hyphen-prefixed for others).
        """
        if self.environment == DeploymentEnvironment.PROD:
            return ""
        return f"-{self.environment.value}"

    def get_service_name_with_env(self) -> str:
        """Get service name with environment suffix.

        Returns:
            str: Service name with optional environment suffix.
        """
        return f"{self.service_name}{self.get_environment_suffix()}"


@dataclass
class DeploymentResult:
    """Result of a Cloud Run deployment operation.

    Attributes:
        success: Whether deployment succeeded.
        service_name: Deployed service name.
        service_url: HTTPS URL of deployed service.
        revision: Cloud Run revision ID.
        deployment_time_seconds: Time taken for deployment.
        image_uri: Container image URI deployed.
        message: Informational message.
    """

    success: bool
    service_name: str
    service_url: str | None = None
    revision: str | None = None
    deployment_time_seconds: float = 0.0
    image_uri: str | None = None
    message: str = ""


class CloudRunDeploymentManager:
    """Manager for Cloud Run deployment operations.

    This class orchestrates the deployment of the extraction API to Cloud Run
    with support for multiple environments, traffic splitting, and monitoring.

    Attributes:
        config: Deployment configuration.
    """

    def __init__(self, config: CloudRunConfig) -> None:
        """Initialize deployment manager.

        Args:
            config: Cloud Run deployment configuration.
        """
        self.config = config
        logger.info(
            "CloudRunDeploymentManager initialized for %s in %s",
            config.service_name,
            config.region,
        )

    def validate_configuration(self) -> bool:
        """Validate deployment configuration.

        Returns:
            bool: True if configuration is valid.

        Raises:
            ValueError: If configuration is invalid.
        """
        logger.debug("Validating deployment configuration")

        if not self.config.project_id.strip():
            msg = "project_id cannot be empty"
            raise ValueError(msg)
        if not self.config.region.strip():
            msg = "region cannot be empty"
            raise ValueError(msg)
        if not self.config.image_uri.strip():
            msg = "image_uri cannot be empty"
            raise ValueError(msg)

        logger.debug("Configuration validation passed")
        return True

    def get_deployment_command(self) -> str:
        """Generate gcloud command for deployment.

        Returns:
            str: gcloud run deploy command.
        """
        command_parts = [
            "gcloud",
            "run",
            "deploy",
            self.config.get_service_name_with_env(),
            f"--image={self.config.image_uri}",
            f"--region={self.config.region}",
            "--platform=managed",
            f"--memory={self.config.memory.value}",
            f"--cpu={self.config.cpu.value}",
            f"--timeout={self.config.timeout_seconds}",
            f"--project={self.config.project_id}",
        ]

        if self.config.max_instances:
            command_parts.append(f"--max-instances={self.config.max_instances}")

        if self.config.min_instances is not None:
            command_parts.append(f"--min-instances={self.config.min_instances}")

        if self.config.enable_authentication:
            command_parts.append("--require-authentication")
        else:
            command_parts.append("--allow-unauthenticated")

        # Add labels
        if self.config.labels:
            labels_str = ",".join(
                [f"{k}={v}" for k, v in self.config.labels.items()],
            )
            command_parts.append(f"--labels={labels_str}")

        # Add environment variables
        if self.config.environment_variables:
            for key, value in self.config.environment_variables.items():
                command_parts.append(f"--set-env-vars={key}={value}")

        return " ".join(command_parts)

    def get_rollback_command(self, revision: str) -> str:
        """Generate gcloud command for rollback to previous revision.

        Args:
            revision: Cloud Run revision to rollback to.

        Returns:
            str: gcloud command for traffic routing.
        """
        return (
            f"gcloud run services update-traffic "
            f"{self.config.get_service_name_with_env()} "
            f"--to-revisions={revision}=100 "
            f"--region={self.config.region} "
            f"--project={self.config.project_id}"
        )

    def get_canary_deployment_command(
        self,
        *,
        new_revision_traffic: int = 10,
    ) -> str:
        """Generate command for canary deployment (traffic split).

        Args:
            new_revision_traffic: Percentage of traffic to new revision (0-100).

        Returns:
            str: gcloud command for traffic split.
        """
        if not 0 <= new_revision_traffic <= MAX_TRAFFIC_PERCENTAGE:
            msg = f"new_revision_traffic must be between 0 and {MAX_TRAFFIC_PERCENTAGE}"
            raise ValueError(msg)

        return (
            f"gcloud run services update-traffic "
            f"{self.config.get_service_name_with_env()} "
            f"--to-revisions=LATEST={new_revision_traffic} "
            f"--region={self.config.region} "
            f"--project={self.config.project_id}"
        )

    def log_deployment_config(self) -> None:
        """Log deployment configuration for audit trail."""
        logger.info("Deployment Configuration:")
        logger.info("  Service: %s", self.config.get_service_name_with_env())
        logger.info("  Project: %s", self.config.project_id)
        logger.info("  Region: %s", self.config.region)
        logger.info("  Environment: %s", self.config.environment.value)
        logger.info("  Memory: %s", self.config.memory.value)
        logger.info("  CPU: %s", self.config.cpu.value)
        logger.info("  Timeout: %ds", self.config.timeout_seconds)
        logger.info("  Max Instances: %s", self.config.max_instances or "unlimited")
        logger.info("  Min Instances: %s", self.config.min_instances or "0")
        logger.info("  Authentication Required: %s", self.config.enable_authentication)
        logger.info("  Image: %s", self.config.image_uri)


def create_prod_config(
    *,
    project_id: str,
    image_uri: str,
    labels: dict[str, str] | None = None,
) -> CloudRunConfig:
    """Factory function to create production Cloud Run configuration.

    Args:
        project_id: GCP project ID.
        image_uri: Container image URI.
        labels: Custom labels for resource tracking.

    Returns:
        CloudRunConfig: Production configuration.
    """
    return CloudRunConfig(
        project_id=project_id,
        region="us-central1",
        service_name="extraction-api",
        image_uri=image_uri,
        environment=DeploymentEnvironment.PROD,
        memory=CloudRunMemory.LARGE,
        cpu=CloudRunCPU.TWO,
        timeout_seconds=600,
        max_instances=100,
        min_instances=2,
        enable_traffic_split=True,
        enable_authentication=True,
        labels=labels or {"environment": "production", "component": "extraction-api"},
        environment_variables={
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "INFO",
        },
    )


def create_staging_config(
    *,
    project_id: str,
    image_uri: str,
    labels: dict[str, str] | None = None,
) -> CloudRunConfig:
    """Factory function to create staging Cloud Run configuration.

    Args:
        project_id: GCP project ID.
        image_uri: Container image URI.
        labels: Custom labels for resource tracking.

    Returns:
        CloudRunConfig: Staging configuration.
    """
    return CloudRunConfig(
        project_id=project_id,
        region="us-central1",
        service_name="extraction-api",
        image_uri=image_uri,
        environment=DeploymentEnvironment.STAGING,
        memory=CloudRunMemory.MEDIUM,
        cpu=CloudRunCPU.TWO,
        timeout_seconds=300,
        max_instances=50,
        min_instances=1,
        enable_traffic_split=False,
        enable_authentication=True,
        labels=labels or {"environment": "staging", "component": "extraction-api"},
        environment_variables={
            "ENVIRONMENT": "staging",
            "LOG_LEVEL": "DEBUG",
        },
    )


def create_dev_config(
    *,
    project_id: str,
    image_uri: str,
    labels: dict[str, str] | None = None,
) -> CloudRunConfig:
    """Factory function to create development Cloud Run configuration.

    Args:
        project_id: GCP project ID.
        image_uri: Container image URI.
        labels: Custom labels for resource tracking.

    Returns:
        CloudRunConfig: Development configuration.
    """
    return CloudRunConfig(
        project_id=project_id,
        region="us-central1",
        service_name="extraction-api",
        image_uri=image_uri,
        environment=DeploymentEnvironment.DEV,
        memory=CloudRunMemory.SMALL,
        cpu=CloudRunCPU.ONE,
        timeout_seconds=300,
        max_instances=10,
        min_instances=0,
        enable_traffic_split=False,
        enable_authentication=False,
        labels=labels or {"environment": "dev", "component": "extraction-api"},
        environment_variables={
            "ENVIRONMENT": "dev",
            "LOG_LEVEL": "DEBUG",
        },
    )
