"""Integration tests for tenant-aware memory flow isolation."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

import src.memory.api as memory_api

if TYPE_CHECKING:
    from collections.abc import Callable

from src.memory.api import MemoryAPI


@dataclass(slots=True)
class _ContextTurnRecord:
    """Seed data used by the fake database for context retrieval."""

    tenant_id: str
    session_id: str
    turn_id: str
    role: str
    content: str
    weight: float
    created_at: datetime
    rel_type: str = "HAS_TURN"


class _ManagedResource(AbstractContextManager[object]):
    """Minimal context manager wrapper used by the fake database."""

    def __init__(self, resource: object) -> None:
        """Store the wrapped resource.

        Args:
            resource: Resource returned from ``__enter__``.
        """
        self._resource = resource

    def __enter__(self) -> object:
        """Return the wrapped resource."""
        return self._resource

    def __exit__(self, *args: object) -> None:
        """No-op exit hook for compatibility with ``with`` blocks."""


@dataclass(slots=True)
class _FakeMemoryDatabase:
    """In-memory stand-in for the subset of Spanner used by ``MemoryAPI``."""

    nodes: list[dict[str, object]] = field(default_factory=list)
    edges: list[dict[str, object]] = field(default_factory=list)
    audit_events: list[dict[str, object]] = field(default_factory=list)
    context_turns: list[_ContextTurnRecord] = field(default_factory=list)

    def batch(self) -> _ManagedResource:
        """Return a batch context manager for write operations."""
        return _ManagedResource(_FakeBatch(self))

    def snapshot(self) -> _ManagedResource:
        """Return a snapshot context manager for read operations."""
        return _ManagedResource(_FakeSnapshot(self))

    def run_in_transaction(
        self,
        callback: Callable[[_FakeTransaction], object],
    ) -> object:
        """Execute a transaction callback against the fake database."""
        return callback(_FakeTransaction(self))

    def seed_context_turns(
        self,
        *,
        tenant_id: str,
        session_id: str,
        turns: list[tuple[str, str, str, float]],
    ) -> None:
        """Seed tenant-scoped context turns for graph retrieval.

        Args:
            tenant_id: Tenant that owns the turns.
            session_id: Session associated with the turns.
            turns: Turn tuples of ``(turn_id, role, content, weight)``.
        """
        for index, (turn_id, role, content, weight) in enumerate(turns):
            self.context_turns.append(
                _ContextTurnRecord(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    turn_id=turn_id,
                    role=role,
                    content=content,
                    weight=weight,
                    created_at=datetime(2026, 1, 1, 0, 0, index, tzinfo=UTC),
                )
            )


@dataclass(slots=True)
class _FakeBatch:
    """Batch writer that interprets the SQL shapes used in the memory layer."""

    database: _FakeMemoryDatabase

    def execute_update(self, sql: str, params: dict[str, object]) -> int:
        """Apply a tenant-aware write mutation to the fake database.

        Args:
            sql: SQL statement shape emitted by the memory layer.
            params: Bound parameters for the statement.

        Returns:
            int: Number of affected records.
        """
        normalized_sql = " ".join(sql.split())
        if "INSERT INTO MemoryNode" in normalized_sql:
            self.database.nodes.append(
                {
                    "node_id": params["node_id"],
                    "tenant_id": params["tenant_id"],
                    "tier": params["tier"],
                    "label": params["label"],
                    "weight": params["weight"],
                    "attributes": params["attributes"],
                    "session_action_count": 0,
                }
            )
            return 1
        if "INSERT INTO MemoryEdge" in normalized_sql:
            self.database.edges.append(
                {
                    "source_id": params["source_id"],
                    "tenant_id": params["tenant_id"],
                    "edge_id": params["edge_id"],
                    "dest_id": params["dest_id"],
                    "rel_type": params["rel_type"],
                }
            )
            return 1
        if "INSERT INTO AUDIT_EVENTS" in normalized_sql:
            self.database.audit_events.append(dict(params))
            return 1
        if normalized_sql.startswith("UPDATE MemoryNode") and (
            "SessionActionCount" in normalized_sql
        ):
            updated_count = 0
            for node in self.database.nodes:
                if (
                    node["tenant_id"] == params["tenant_id"]
                    and node["tier"] == params["tier"]
                    and node["node_id"] == params["session_id"]
                ):
                    node["session_action_count"] = int(node.get("session_action_count", 0)) + 1
                    updated_count += 1
            return updated_count
        if normalized_sql.startswith("UPDATE MemoryNode"):
            updated_count = 0
            for node in self.database.nodes:
                if (
                    node["tenant_id"] == params["tenant_id"]
                    and node["tier"] == params["tier"]
                    and node["node_id"] in params["node_ids"]
                ):
                    node["weight"] = float(node["weight"]) + float(params["delta"])
                    updated_count += 1
            return updated_count
        msg = f"Unexpected SQL in fake batch: {normalized_sql}"
        raise AssertionError(msg)


@dataclass(slots=True)
class _FakeSnapshot:
    """Snapshot reader that enforces tenant-scoped reads."""

    database: _FakeMemoryDatabase

    def execute_sql(self, sql: str, params: dict[str, object]) -> list[tuple[object, ...]]:
        """Execute a tenant-aware read against the fake database.

        Args:
            sql: SQL or graph query emitted by the memory layer.
            params: Bound parameters for the query.

        Returns:
            list[tuple[object, ...]]: Query result rows.
        """
        normalized_sql = " ".join(sql.split())
        tenant_id = str(params["tenant_id"])
        if normalized_sql.startswith("SELECT MemoryTier FROM MemoryNode"):
            matching_node = next(
                (
                    node
                    for node in self.database.nodes
                    if node["tenant_id"] == tenant_id and node["node_id"] == params["node_id"]
                ),
                None,
            )
            if matching_node is None:
                return []
            return [(matching_node["tier"],)]
        if normalized_sql.startswith("SELECT SessionActionCount FROM MemoryNode"):
            matching_node = next(
                (
                    node
                    for node in self.database.nodes
                    if node["tenant_id"] == tenant_id and node["node_id"] == params["session_id"]
                ),
                None,
            )
            if matching_node is None:
                return []
            return [(matching_node.get("session_action_count", 0),)]
        if normalized_sql.startswith("MATCH p = (s:Node)-[e]->(t:Node)"):
            matching_turns = [
                turn
                for turn in self.database.context_turns
                if turn.tenant_id == tenant_id and turn.session_id == params["session_id"]
            ]
            ordered_turns = sorted(matching_turns, key=lambda turn: turn.created_at, reverse=True)
            limited_turns = ordered_turns[: int(params["window_size"])]
            return [
                (
                    turn.turn_id,
                    turn.role,
                    turn.content,
                    turn.weight,
                    turn.created_at,
                    turn.rel_type,
                )
                for turn in limited_turns
            ]
        msg = f"Unexpected SQL in fake snapshot: {normalized_sql}"
        raise AssertionError(msg)


@dataclass(slots=True)
class _FakeTransaction:
    """Transaction shim that reuses the fake batch and snapshot behavior."""

    database: _FakeMemoryDatabase

    def execute_sql(self, sql: str, params: dict[str, object]) -> list[tuple[object, ...]]:
        """Delegate read execution to the snapshot fake."""
        return _FakeSnapshot(self.database).execute_sql(sql, params)

    def execute_update(self, sql: str, params: dict[str, object]) -> int:
        """Delegate write execution to the batch fake."""
        return _FakeBatch(self.database).execute_update(sql, params)


class TestTenantIsolatedMemoryFlow:
    """Integration tests for tenant isolation across the memory API flow."""

    @pytest.fixture(autouse=True)
    def _configure_fake_database(self) -> object:
        """Provide a shared fake database and apply API dependency override."""
        self._fake_database = _FakeMemoryDatabase()
        original_get_database = memory_api.SpannerClient.get_database
        memory_api.SpannerClient.get_database = lambda: self._fake_database

        try:
            yield
        finally:
            memory_api.SpannerClient.get_database = original_get_database

    async def test_full_memory_flow_isolates_same_session_id_across_tenants(
        self,
    ) -> None:
        """Sessions with the same identifier must remain isolated by tenant."""
        await MemoryAPI.create_session(
            tenant_id="tenant_a",
            session_id="session_shared",
            user_id="user_a",
        )
        await MemoryAPI.create_session(
            tenant_id="tenant_b",
            session_id="session_shared",
            user_id="user_b",
        )
        await MemoryAPI.add_semantic_fact(
            tenant_id="tenant_a",
            entity_type="PERSON",
            entity_id="entity_a",
            relationship={"source_id": "session_shared", "type": "REFERENCES"},
        )
        await MemoryAPI.add_semantic_fact(
            tenant_id="tenant_b",
            entity_type="PERSON",
            entity_id="entity_b",
            relationship={"source_id": "session_shared", "type": "REFERENCES"},
        )

        self._fake_database.seed_context_turns(
            tenant_id="tenant_a",
            session_id="session_shared",
            turns=[
                ("turn_a_1", "User", '{"content": "alpha"}', 0.60),
                ("turn_a_2", "Agent", '{"content": "alpha reply"}', 0.55),
            ],
        )
        self._fake_database.seed_context_turns(
            tenant_id="tenant_b",
            session_id="session_shared",
            turns=[("turn_b_1", "User", '{"content": "beta"}', 0.65)],
        )

        response_a = await MemoryAPI.retrieve_context_window(
            tenant_id="tenant_a",
            session_id="session_shared",
            window_size=10,
        )
        response_b = await MemoryAPI.retrieve_context_window(
            tenant_id="tenant_b",
            session_id="session_shared",
            window_size=10,
        )

        assert response_a.tenant_id == "tenant_a"
        assert response_b.tenant_id == "tenant_b"
        assert [turn.content for turn in response_a.turns] == [
            '{"content": "alpha reply"}',
            '{"content": "alpha"}',
        ]
        assert [turn.content for turn in response_b.turns] == ['{"content": "beta"}']
        assert {
            node["tenant_id"]
            for node in self._fake_database.nodes
            if node["node_id"] == "session_shared"
        } == {"tenant_a", "tenant_b"}
        assert {edge["tenant_id"] for edge in self._fake_database.edges} == {
            "tenant_a",
            "tenant_b",
        }
        assert {event["tenant_id"] for event in self._fake_database.audit_events} == {
            "tenant_a",
            "tenant_b",
        }

    async def test_relationship_lookup_rejects_cross_tenant_source_node(
        self,
    ) -> None:
        """A tenant must not be able to attach relationships to another tenant's nodes."""
        await MemoryAPI.create_session(
            tenant_id="tenant_a",
            session_id="session_shared",
            user_id="user_a",
        )

        with pytest.raises(ValueError, match="not found in tenant"):
            await MemoryAPI.add_semantic_fact(
                tenant_id="tenant_b",
                entity_type="PERSON",
                entity_id="entity_b",
                relationship={"source_id": "session_shared", "type": "REFERENCES"},
            )

        assert all(
            node["tenant_id"] != "tenant_b"
            for node in self._fake_database.nodes
            if node["node_id"] == "session_shared"
        )
        assert self._fake_database.edges == []
