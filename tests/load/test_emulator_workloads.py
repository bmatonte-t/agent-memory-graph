"""Load-oriented emulator workload tests for the real Spanner-backed memory API."""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from src.db.schema import SchemaManager
from src.db.spanner_client import SpannerClient
from src.memory.api import MemoryAPI
from src.models.schemas import ContextResponse, FactResponse, SessionResponse

if TYPE_CHECKING:
    from collections.abc import Iterator

DEFAULT_PROJECT_ID = "test-project"
DEFAULT_INSTANCE_ID = "test-instance"
DEFAULT_DATABASE_ID = "test-database"
SEQUENTIAL_FACT_COUNT = 24
CONCURRENT_FACT_COUNT = 10
SEQUENTIAL_MAX_ELAPSED_MS = 30_000.0
CONTEXT_WINDOW_SIZE = 10
ENTITY_TYPE = "OBJECT"
RELATIONSHIP_TYPE = "REFERENCES"


@dataclass(slots=True)
class EmulatorRuntime:
    """Resolved Spanner emulator connection settings for a test run."""

    project_id: str
    instance_id: str
    database_id: str


def _build_unique_id(prefix: str) -> str:
    """Create a collision-resistant identifier for emulator workload tests.

    Args:
        prefix: Stable identifier prefix for the generated value.

    Returns:
        str: Unique identifier safe for tenant, session, or entity ids.
    """
    return f"{prefix}_{uuid.uuid4().hex}"


@pytest.fixture
def spanner_emulator_runtime() -> Iterator[EmulatorRuntime]:
    """Initialize the real Spanner client against the local emulator.

    Skips cleanly when the emulator host is not configured.

    Yields:
        Iterator[EmulatorRuntime]: Resolved runtime configuration for the test.
    """
    emulator_host = os.getenv("SPANNER_EMULATOR_HOST")
    if not emulator_host:
        pytest.skip("SPANNER_EMULATOR_HOST is not set; skipping emulator workload tests")

    os.environ.setdefault("GCP_PROJECT_ID", DEFAULT_PROJECT_ID)
    os.environ.setdefault("SPANNER_INSTANCE_ID", DEFAULT_INSTANCE_ID)
    os.environ.setdefault("SPANNER_DATABASE_ID", DEFAULT_DATABASE_ID)

    runtime = EmulatorRuntime(
        project_id=os.environ["GCP_PROJECT_ID"],
        instance_id=os.environ["SPANNER_INSTANCE_ID"],
        database_id=os.environ["SPANNER_DATABASE_ID"],
    )

    SpannerClient.close()
    SpannerClient.initialize(
        project_id=runtime.project_id,
        instance_id=runtime.instance_id,
        database_id=runtime.database_id,
    )
    SchemaManager.init_schema(SpannerClient.get_database())

    yield runtime

    SpannerClient.close()


class TestEmulatorWorkloads:
    """Exercise real emulator-backed memory workloads without mocks."""

    async def test_sequential_semantic_fact_writes_complete_within_threshold(
        self,
        spanner_emulator_runtime: EmulatorRuntime,
    ) -> None:
        """Sequential semantic fact writes should succeed within a pragmatic emulator budget.

        Args:
            spanner_emulator_runtime: Initialized emulator-backed Spanner runtime.
        """
        del spanner_emulator_runtime
        tenant_id = _build_unique_id("tenant_seq")
        session_id = _build_unique_id("session_seq")
        user_id = _build_unique_id("user_seq")

        session_response = await MemoryAPI.create_session(
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
            metadata={"workload": "sequential"},
        )

        assert isinstance(session_response, SessionResponse)
        assert session_response.tenant_id == tenant_id
        assert session_response.session_id == session_id

        started = time.perf_counter()
        results: list[FactResponse] = []
        for index in range(SEQUENTIAL_FACT_COUNT):
            entity_id = _build_unique_id(f"entity_seq_{index}")
            fact_response = await MemoryAPI.add_semantic_fact(
                tenant_id=tenant_id,
                entity_type=ENTITY_TYPE,
                entity_id=entity_id,
                attributes={"sequence": index, "mode": "sequential"},
                relationship={"source_id": session_id, "type": RELATIONSHIP_TYPE},
                session_id=session_id,
            )
            results.append(fact_response)
        elapsed_ms = (time.perf_counter() - started) * 1000

        assert len(results) == SEQUENTIAL_FACT_COUNT
        assert all(isinstance(result, FactResponse) for result in results)
        assert all(result.tenant_id == tenant_id for result in results)
        assert elapsed_ms < SEQUENTIAL_MAX_ELAPSED_MS

    async def test_concurrent_mixed_workload_writes_and_context_retrieval(
        self,
        spanner_emulator_runtime: EmulatorRuntime,
    ) -> None:
        """Concurrent semantic writes should succeed and allow valid context retrieval.

        Args:
            spanner_emulator_runtime: Initialized emulator-backed Spanner runtime.
        """
        del spanner_emulator_runtime
        tenant_id = _build_unique_id("tenant_concurrent")
        session_id = _build_unique_id("session_concurrent")
        user_id = _build_unique_id("user_concurrent")

        session_response = await MemoryAPI.create_session(
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
            metadata={"workload": "concurrent"},
        )

        assert isinstance(session_response, SessionResponse)
        assert session_response.tenant_id == tenant_id
        assert session_response.session_id == session_id

        async def _write_fact(index: int) -> FactResponse:
            """Write one fact linked to the session under test.

            Args:
                index: Sequence index for the workload item.

            Returns:
                FactResponse: Persisted fact descriptor.
            """
            return await MemoryAPI.add_semantic_fact(
                tenant_id=tenant_id,
                entity_type=ENTITY_TYPE,
                entity_id=_build_unique_id(f"entity_concurrent_{index}"),
                attributes={"sequence": index, "mode": "concurrent"},
                relationship={"source_id": session_id, "type": RELATIONSHIP_TYPE},
                session_id=session_id,
            )

        write_results = await asyncio.gather(
            *(_write_fact(index) for index in range(CONCURRENT_FACT_COUNT)),
            return_exceptions=True,
        )

        assert len(write_results) == CONCURRENT_FACT_COUNT
        assert not any(isinstance(result, Exception) for result in write_results)

        fact_results = [result for result in write_results if isinstance(result, FactResponse)]
        assert len(fact_results) == CONCURRENT_FACT_COUNT
        assert all(result.tenant_id == tenant_id for result in fact_results)

        context_response = await MemoryAPI.retrieve_context_window(
            tenant_id=tenant_id,
            session_id=session_id,
            window_size=CONTEXT_WINDOW_SIZE,
        )

        assert isinstance(context_response, ContextResponse)
        assert context_response.tenant_id == tenant_id
        assert context_response.session_id == session_id
        assert isinstance(context_response.turns, list)
