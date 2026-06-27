"""Shared test fixtures and configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from pathlib import Path

import uuid

from src.models.agent import AgentOrchestrationRequest
from src.models.mcp import MCPInvokeRequest, MCPToolName
from src.models.schemas import (
    AddSemanticFactRequest,
    CreateSessionRequest,
    RecordAuditEventRequest,
    RetrieveContextWindowRequest,
)


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
    config_data = {
        "logging": {"log_level": "INFO", "third_party_log_level": "WARNING"},
        "cloud_trace": {"enabled": True},
        "cloud_logging": {"enabled": True},
        "governance": {
            "weighting": {"enabled": True, "action_count_threshold": 5},
            "authorization": {"enabled": True, "default_deny": True},
        },
    }
    config_file.write_text(yaml.dump(config_data))
    return config_file


@pytest.fixture
def tenant_id() -> str:
    """Provide a test tenant identifier."""
    return "tenant_test_1"


@pytest.fixture
def session_id() -> str:
    """Provide a test session identifier."""
    return str(uuid.uuid4())


@pytest.fixture
def user_id() -> str:
    """Provide a test user identifier."""
    return "user_test_1"


@pytest.fixture
def request_id() -> str:
    """Provide a test request identifier."""
    return str(uuid.uuid4())


@pytest.fixture
def create_session_request(tenant_id: str, session_id: str, user_id: str) -> CreateSessionRequest:
    """Provide a CreateSessionRequest for testing."""
    return CreateSessionRequest(
        tenant_id=tenant_id,
        session_id=session_id,
        user_id=user_id,
    )


@pytest.fixture
def add_semantic_fact_request(tenant_id: str) -> AddSemanticFactRequest:
    """Provide an AddSemanticFactRequest for testing."""
    return AddSemanticFactRequest(
        tenant_id=tenant_id,
        entity_type="PERSON",
        entity_id="entity_test_1",
        attributes={"name": "Test Entity"},
    )


@pytest.fixture
def record_audit_event_request(tenant_id: str, session_id: str) -> RecordAuditEventRequest:
    """Provide a RecordAuditEventRequest for testing."""
    return RecordAuditEventRequest(
        tenant_id=tenant_id,
        event_type="TEST_EVENT",
        source_node_id=session_id,
        context={"test": "context"},
    )


@pytest.fixture
def retrieve_context_window_request(
    tenant_id: str, session_id: str
) -> RetrieveContextWindowRequest:
    """Provide a RetrieveContextWindowRequest for testing."""
    return RetrieveContextWindowRequest(
        tenant_id=tenant_id,
        session_id=session_id,
        window_size=10,
    )


@pytest.fixture
def mcp_invoke_request(tenant_id: str, session_id: str, request_id: str) -> MCPInvokeRequest:
    """Provide an MCPInvokeRequest for testing."""
    return MCPInvokeRequest(
        tenant_id=tenant_id,
        tool_name=MCPToolName.MEMORY_SEARCH,
        arguments={"query": "test query"},
        session_id=session_id,
        request_id=request_id,
    )


@pytest.fixture
def agent_orchestration_request(
    tenant_id: str,
    session_id: str,
    request_id: str,
) -> AgentOrchestrationRequest:
    """Provide an AgentOrchestrationRequest for testing."""
    return AgentOrchestrationRequest(
        tenant_id=tenant_id,
        prompt="What is test?",
        session_id=session_id,
        request_id=request_id,
    )
