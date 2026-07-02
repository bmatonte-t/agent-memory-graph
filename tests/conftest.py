"""Shared test fixtures and configuration."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import yaml

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path
    from typing import Protocol

    class HttpServerLike(Protocol):
        """Protocol for pytest http server fixtures exposing url_for."""

        def url_for(self, path: str) -> str:
            """Build a full URL for the provided path."""
            ...


from src.models.agent import AgentOrchestrationRequest
from src.models.mcp import MCPInvokeRequest, MCPToolName
from src.models.schemas import (
    AddSemanticFactRequest,
    ContextResponse,
    ContextTurn,
    CreateSessionRequest,
    RecordAuditEventRequest,
    RetrieveContextWindowRequest,
)
from src.project_base.settings.config import SingleCompanySettings
from src.security import governance_adapter


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
        relationship=None,
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


SINGLE_COMPANY_ID = "test-org"
"""Fixed company identifier used across single-company mode fixtures."""


@pytest.fixture
def single_company_settings() -> Generator[SingleCompanySettings]:
    """Activate org-wide single-company mode with a fixed company identifier.

    Patches ``settings.single_company`` so that ``validate_tenant_id(None)``
    returns ``SINGLE_COMPANY_ID`` and no ``tenant_id`` is required in requests.

    Also clears the governance adapter cache so each test gets a fresh adapter.
    """
    from src.project_base.settings import settings  # noqa: PLC0415

    org_settings = SingleCompanySettings(enabled=True, company_id=SINGLE_COMPANY_ID)
    governance_adapter._ADAPTER_CACHE.clear()

    with patch.object(settings, "single_company", org_settings):
        yield org_settings

    governance_adapter._ADAPTER_CACHE.clear()


@pytest.fixture
def external_auth_settings(httpserver: HttpServerLike) -> Generator[HttpServerLike]:
    """Activate org-wide mode with an external passthrough auth adapter.

    Requires ``pytest-localserver`` or ``pytest-httpserver`` to provide
    ``httpserver``.  The fixture yields the mock server so tests can configure
    response stubs.
    """
    from src.project_base.settings import settings  # noqa: PLC0415

    org_settings = SingleCompanySettings(
        enabled=True,
        company_id=SINGLE_COMPANY_ID,
        auth_mode="external",
        external_auth_url=httpserver.url_for("/authorize"),
    )
    governance_adapter._ADAPTER_CACHE.clear()

    with patch.object(settings, "single_company", org_settings):
        yield httpserver

    governance_adapter._ADAPTER_CACHE.clear()


def _derive_markers_from_path(test_path: Path) -> set[str]:
    """Infer default pytest markers from the test file path.

    Args:
        test_path: Path of the collected test item.

    Returns:
        set[str]: Marker names inferred from the path and file name.
    """
    absolute_path = test_path.as_posix()
    relative_path = absolute_path.replace("\\", "/")
    marker_names: set[str] = set()

    if "/tests/unit/" in relative_path or relative_path.startswith("tests/unit/"):
        marker_names.add("unit")

    if "/tests/integration/" in relative_path or relative_path.startswith("tests/integration/"):
        marker_names.add("integration")

    if "/tests/load/" in relative_path or relative_path.startswith("tests/load/"):
        marker_names.add("load")

    if "/tests/chaos/" in relative_path or relative_path.startswith("tests/chaos/"):
        marker_names.add("chaos")

    # Keep legacy top-level tests (tests/test_*.py) inside functional gates by
    # default so they are not excluded from marker-based CI confidence checks.
    is_top_level_test = (
        (relative_path.startswith("tests/test_") or "/tests/test_" in relative_path)
        and "/tests/unit/" not in relative_path
        and "/tests/integration/" not in relative_path
        and "/tests/load/" not in relative_path
        and "/tests/chaos/" not in relative_path
    )
    if is_top_level_test:
        marker_names.add("unit")

    file_name = test_path.name.lower()
    if "performance" in file_name:
        marker_names.add("performance")

    return marker_names


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply default layer markers from file paths when tests omit explicit markers.

    This keeps marker-based gates reliable without forcing repetitive per-test
    decorators, while still allowing explicit markers to coexist.

    Args:
        config: Pytest configuration object.
        items: Collected pytest items.
    """
    del config
    for item in items:
        derived_markers = _derive_markers_from_path(item.path)
        existing_markers = {marker.name for marker in item.iter_markers()}

        for marker_name in derived_markers - existing_markers:
            item.add_marker(marker_name)


@pytest.fixture
def context_turn_row_factory() -> Callable[..., tuple[str, str, str, float, datetime, str]]:
    """Build canonical DB rows used by context-window tests.

    Returns:
        Callable[..., tuple[str, str, str, float, datetime, str]]: Factory that
        returns one context row tuple in DB result shape.
    """

    def _factory(
        *,
        turn_id: str,
        role: str,
        content: str,
        weight: float,
    ) -> tuple[str, str, str, float, datetime, str]:
        return (
            turn_id,
            role,
            json.dumps({"content": content}),
            weight,
            datetime.now(UTC),
            "HAS_TURN",
        )

    return _factory


@pytest.fixture
def context_response_factory() -> Callable[..., ContextResponse]:
    """Build canonical `ContextResponse` payloads for memory API tests.

    Returns:
        Callable[..., ContextResponse]: Factory that generates consistent
        context envelopes from compact turn tuples.
    """

    def _factory(
        *,
        tenant_id: str,
        session_id: str,
        turns: list[tuple[str, str, str, float]],
    ) -> ContextResponse:
        retrieved_at = datetime.now(UTC)
        context_turns = [
            ContextTurn(
                turn_id=turn_id,
                node_id=turn_id,
                tenant_id=tenant_id,
                role=role,
                content=json.dumps({"content": content}),
                weight=weight,
                created_at=retrieved_at,
            )
            for turn_id, role, content, weight in turns
        ]

        return ContextResponse(
            tenant_id=tenant_id,
            session_id=session_id,
            turns=context_turns,
            total_weight_sum=sum(turn.weight for turn in context_turns),
            retrieved_at=retrieved_at,
        )

    return _factory
