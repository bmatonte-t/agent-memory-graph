"""Tests for the settings module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from src.project_base.settings import ENVIRONMENT_VARIABLE_PREFIX, Environment
from src.project_base.settings._core import runtime_environment
from src.project_base.settings.config import Settings
from src.project_base.settings.enums import LogLevel
from src.project_base.settings.models import Logging
from src.security.governance import GovernanceSettings, WeightingTriggerPolicy

EXPECTED_WEIGHTING_THRESHOLD = 7

if TYPE_CHECKING:
    from pathlib import Path


class TestSettings:
    """Tests for Settings class."""

    def test_requires_environment(self) -> None:
        """Test that Settings requires environment parameter."""
        with pytest.raises(TypeError, match="environment"):
            Settings()  # type: ignore[call-arg]

    def test_with_environment(self) -> None:
        """Test that Settings can be instantiated with environment."""
        logging = Logging(log_level=LogLevel.INFO, third_party_log_level=LogLevel.WARNING)
        governance = GovernanceSettings(
            weighting=WeightingTriggerPolicy(enabled=True, action_count_threshold=5)
        )
        config = Settings(
            environment=Environment.DEV,
            logging=logging,
            governance=governance,
        )
        assert config.environment == Environment.DEV
        assert config.logging.log_level == LogLevel.INFO
        assert config.logging.third_party_log_level == LogLevel.WARNING
        assert config.governance.weighting.should_trigger(5) is True

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables override defaults."""
        monkeypatch.setenv(f"{ENVIRONMENT_VARIABLE_PREFIX}LOGGING__LOG_LEVEL", "ERROR")
        monkeypatch.setenv(
            f"{ENVIRONMENT_VARIABLE_PREFIX}LOGGING__THIRD_PARTY_LOG_LEVEL", "CRITICAL"
        )
        monkeypatch.setenv(
            f"{ENVIRONMENT_VARIABLE_PREFIX}GOVERNANCE__WEIGHTING__ENABLED",
            "true",
        )
        monkeypatch.setenv(
            f"{ENVIRONMENT_VARIABLE_PREFIX}GOVERNANCE__WEIGHTING__ACTION_COUNT_THRESHOLD",
            "7",
        )
        monkeypatch.setenv(f"{ENVIRONMENT_VARIABLE_PREFIX}ENVIRONMENT", "dev")

        # Don't pass logging parameter - let it load from env vars
        config = Settings(environment=Environment.DEV)  # type: ignore[call-arg]
        assert config.logging.log_level == LogLevel.ERROR
        assert config.logging.third_party_log_level == LogLevel.CRITICAL
        assert config.governance.weighting.enabled is True
        assert config.governance.weighting.action_count_threshold == EXPECTED_WEIGHTING_THRESHOLD


class TestYAMLLoading:
    """Tests for YAML configuration loading."""

    def test_loads_base_yaml(self, base_yaml_config: Path, temp_config_dir: Path) -> None:
        """Test that base config.yaml is loaded."""
        with patch("src.project_base.settings._core.ROOT", temp_config_dir):
            config = Settings(environment=Environment.DEV)  # type: ignore[call-arg]
            assert config.logging.log_level == LogLevel.INFO

    def test_env_specific_yaml_overrides_base(
        self,
        base_yaml_config: Path,
        dev_yaml_config: Path,
        temp_config_dir: Path,
    ) -> None:
        """Test that config.dev.yaml overrides config.yaml."""
        with patch("src.project_base.settings._core.ROOT", temp_config_dir):
            config = Settings(environment=Environment.DEV)  # type: ignore[call-arg]
            assert config.logging.log_level == LogLevel.DEBUG

    def test_env_var_overrides_yaml(
        self, base_yaml_config: Path, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that environment variables override YAML config."""
        monkeypatch.setenv(f"{ENVIRONMENT_VARIABLE_PREFIX}LOGGING__LOG_LEVEL", "CRITICAL")

        with patch("src.project_base.settings._core.ROOT", temp_config_dir):
            config = Settings(environment=Environment.DEV)  # type: ignore[call-arg]
            assert config.logging.log_level == LogLevel.CRITICAL

    def test_missing_env_yaml_falls_back_to_base(
        self, base_yaml_config: Path, temp_config_dir: Path
    ) -> None:
        """Test that missing config.prod.yaml falls back to config.yaml."""
        with patch("src.project_base.settings._core.ROOT", temp_config_dir):
            config = Settings(environment=Environment.PROD)  # type: ignore[call-arg]
            # Should fall back to base config.yaml
            assert config.logging.log_level == LogLevel.INFO


class TestLoadingHierarchy:
    """Tests for the complete loading hierarchy."""

    def test_env_vars_override_yaml(
        self,
        base_yaml_config: Path,
        dev_yaml_config: Path,
        temp_config_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that environment variables have highest priority in the hierarchy."""
        monkeypatch.setenv(f"{ENVIRONMENT_VARIABLE_PREFIX}LOGGING__LOG_LEVEL", "ERROR")

        with patch("src.project_base.settings._core.ROOT", temp_config_dir):
            config = Settings(environment=Environment.DEV)  # type: ignore[call-arg]
            # Env var should override config.dev.yaml
            assert config.logging.log_level == LogLevel.ERROR

    def test_env_specific_yaml_overrides_base_yaml(
        self,
        base_yaml_config: Path,
        dev_yaml_config: Path,
        temp_config_dir: Path,
    ) -> None:
        """Test that environment-specific YAML overrides base YAML."""
        with patch("src.project_base.settings._core.ROOT", temp_config_dir):
            config = Settings(environment=Environment.DEV)  # type: ignore[call-arg]
            # config.dev.yaml (DEBUG) should override config.yaml (INFO)
            assert config.logging.log_level == LogLevel.DEBUG


class TestRuntimeEnvironment:
    """Tests for runtime_environment function."""

    def test_default_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that runtime_environment returns DEV by default."""
        monkeypatch.delenv(f"{ENVIRONMENT_VARIABLE_PREFIX}ENVIRONMENT", raising=False)
        assert runtime_environment() == Environment.DEV

    @pytest.mark.parametrize(
        ("env_value", "expected"),
        [
            ("local", Environment.LOCAL),
            ("LOCAL", Environment.LOCAL),
            ("Local", Environment.LOCAL),
            ("dev", Environment.DEV),
            ("DEV", Environment.DEV),
            ("Dev", Environment.DEV),
            ("prod", Environment.PROD),
            ("PROD", Environment.PROD),
            ("Prod", Environment.PROD),
        ],
    )
    def test_valid_environments(
        self, monkeypatch: pytest.MonkeyPatch, env_value: str, expected: Environment
    ) -> None:
        """Test that runtime_environment returns correct Environment for valid values."""
        monkeypatch.setenv(f"{ENVIRONMENT_VARIABLE_PREFIX}ENVIRONMENT", env_value)
        assert runtime_environment() == expected

    @pytest.mark.parametrize(
        "invalid_value",
        [
            "invalid",
            "staging",
            "test",
            "production",
            "",
        ],
    )
    def test_invalid_environment_raises_error(
        self, monkeypatch: pytest.MonkeyPatch, invalid_value: str
    ) -> None:
        """Test that runtime_environment raises ValueError for invalid environment values."""
        monkeypatch.setenv(f"{ENVIRONMENT_VARIABLE_PREFIX}ENVIRONMENT", invalid_value)

        expected_msg = (
            f"Invalid environment '{invalid_value.lower()}' in "
            f"{ENVIRONMENT_VARIABLE_PREFIX}ENVIRONMENT"
        )
        with pytest.raises(ValueError, match=expected_msg):
            runtime_environment()

    def test_error_message_includes_valid_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that error message includes list of valid environment values."""
        monkeypatch.setenv(f"{ENVIRONMENT_VARIABLE_PREFIX}ENVIRONMENT", "invalid")

        with pytest.raises(ValueError, match=r"Must be one of \['local', 'dev', 'prod'\]"):
            runtime_environment()
