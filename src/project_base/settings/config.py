"""Application Settings class; add your settings fields here!

See https://documentation.tryolabs.com/repo-template/batteries/configuration/.

Note: you may store secrets in `.local` or `.env` files.
"""

from src.security.governance import GovernanceSettings

from ._core import PreconfiguredSettings
from .models import CloudLogging, CloudTrace, Logging


class Settings(PreconfiguredSettings):
    """Application settings.

    Sources are loaded with the following priority (highest to lowest):

    - Values passed directly to the constructor (for testing).
    - Environment variables (prefixed with the value of the `ENVIRONMENT_VARIABLE_PREFIX` variable).
    - A `.env` file at the project root.
    - Environment-specific local YAML (`config.{env}.local.yaml`).
    - Environment-specific YAML (`config.{env}.yaml`).
    - Base local YAML (`config.local.yaml`).
    - Base YAML (`config.yaml`).
    - Field default values.
    """

    logging: Logging
    cloud_trace: CloudTrace = CloudTrace()
    cloud_logging: CloudLogging = CloudLogging()
    governance: GovernanceSettings = GovernanceSettings()
