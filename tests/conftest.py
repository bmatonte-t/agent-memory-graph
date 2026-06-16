"""Shared test fixtures and configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory for testing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def base_yaml_config(temp_config_dir: Path) -> Path:
    """Create a base config.yaml file."""
    config_file = temp_config_dir / "config.yaml"
    config_data = {"logging": {"log_level": "INFO", "third_party_log_level": "WARNING"}}
    config_file.write_text(yaml.dump(config_data))
    return config_file


@pytest.fixture
def dev_yaml_config(temp_config_dir: Path) -> Path:
    """Create a config.dev.yaml file."""
    config_file = temp_config_dir / "config.dev.yaml"
    config_data = {"logging": {"log_level": "DEBUG", "third_party_log_level": "DEBUG"}}
    config_file.write_text(yaml.dump(config_data))
    return config_file


@pytest.fixture
def prod_yaml_config(temp_config_dir: Path) -> Path:
    """Create a config.prod.yaml file."""
    config_file = temp_config_dir / "config.prod.yaml"
    config_data = {"logging": {"log_level": "WARNING", "third_party_log_level": "ERROR"}}
    config_file.write_text(yaml.dump(config_data))
    return config_file
