"""Core memory API implementations."""

import json
import logging
import math
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from src.db.schema import SchemaConfig
from src.db.spanner_client import SpannerClient
from src.models.schemas import (
    AuditResponse,
    ContextResponse,
    ContextTurn,
    FactResponse,
    SessionResponse,
)
from src.security.validators import (
    validate_entity_type,
    validate_optional_mapping,
    validate_relationship,
    validate_required_string,
    validate_tenant_id,
    validate_window_size,
)

logger = logging.getLogger(__name__)


class _SpannerBatch(Protocol):
    """Protocol for the subset of batch API used by MemoryAPI."""

    def execute_update(self, sql: str, params: dict[str, Any]) -> int: ...


class MemoryAPI:
    """Core memory API for tripartite memory operations."""

    @staticmethod
    def _enforce_audit_append_only(operation: str) -> None:
        """Validate that audit table mutations remain append-only.

        Args:
            operation: Mutation operation on audit table.

        Raises:
            PermissionError: If the requested operation violates immutability.
        """
        SpannerClient._validate_audit_mutation_forbidden("AUDIT_EVENTS", operation)

    @staticmethod
    def _serialize_json_attributes(attributes: dict[str, Any]) -> str:
        """Serialize attributes payload to JSON string.

        Args:
            attributes: Attribute mapping to persist.

        Returns:
            str: JSON-encoded payload.
        """
        return json.dumps(attributes, separators=(",", ":"), default=str)

    @staticmethod
    def _insert_audit_event_in_batch(
        *,
        batch: _SpannerBatch,
        tenant_id: str,
        event_type: str,
        source_node_id: str,
        context: dict[str, Any] | None,
        timestamp: datetime,
    ) -> AuditResponse:
        """Insert an audit event inside an existing write batch.

        Writes to append-only AUDIT_EVENTS table with tenant isolation.

        Args:
            batch: Active Spanner batch.
            tenant_id: Tenant identifier for isolation.
            event_type: Audit event type.
            source_node_id: Source node identifier.
            context: Optional context payload.
            timestamp: Event timestamp.

        Returns:
            AuditResponse: Created audit event descriptor.

        Raises:
            ValueError: If tenant_id is empty or invalid.
        """
        tenant_id = validate_tenant_id(tenant_id)
        event_type = validate_required_string(event_type, field_name="event_type")
        source_node_id = validate_required_string(source_node_id, field_name="source_node_id")
        context = validate_optional_mapping(context, field_name="context") or None
        MemoryAPI._enforce_audit_append_only("INSERT")
        event_id = str(uuid.uuid4())
        event_attributes = {
            "event_type": event_type,
            "source_node_id": source_node_id,
            **(dict(context) if context else {}),
        }

        sql = """
            INSERT INTO AUDIT_EVENTS (
                EventId, TenantId, SourceNodeId, EventType,
                Attributes, CreatedAt
            ) VALUES (
                @event_id, @tenant_id, @source_node_id, @event_type,
                JSON(@attributes), @now
            )
        """
        batch.execute_update(
            sql,
            {
                "event_id": event_id,
                "tenant_id": tenant_id,
                "source_node_id": source_node_id,
                "event_type": event_type,
                "now": timestamp,
                "attributes": MemoryAPI._serialize_json_attributes(event_attributes),
            },
        )

        return AuditResponse(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            tenant_id=tenant_id,
        )

    @staticmethod
    def _get_node_memory_tier(tenant_id: str, node_id: str) -> str | None:
        """Return memory tier for a node when it exists in the tenant.

        Args:
            tenant_id: Tenant identifier for isolation.
            node_id: Node identifier to inspect.

        Returns:
            str | None: Node memory tier when found in tenant, else None.

        Raises:
            ValueError: If tenant_id is empty or invalid.
            RuntimeError: If database read fails.
        """
        tenant_id = validate_tenant_id(tenant_id)
        node_id = validate_required_string(node_id, field_name="node_id")
        query = """
            SELECT MemoryTier
            FROM MemoryNode
            WHERE TenantId = @tenant_id AND NodeId = @node_id
            LIMIT 1
        """

        try:
            database = SpannerClient.get_database()
            with database.snapshot() as snapshot:
                rows = list(
                    snapshot.execute_sql(
                        query,
                        {"tenant_id": tenant_id, "node_id": node_id},
                    )
                )
        except Exception as error:
            msg = f"Failed to lookup node tier: {error}"
            raise RuntimeError(msg) from error

        if not rows:
            return None

        return rows[0][0]

    @staticmethod
    async def create_session(
        tenant_id: str,
        session_id: str,
        user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionResponse:
        """Create a new session and initialize Context Graph.

        Args:
            tenant_id: Tenant identifier for isolation.
            session_id: Unique session identifier
            user_id: User ID associated with session
            metadata: Optional session metadata

        Returns:
            SessionResponse with session details

        Raises:
            ValueError: If tenant_id, session_id, or user_id is empty or invalid
            RuntimeError: If database write fails
        """
        tenant_id = validate_tenant_id(tenant_id)
        session_id = validate_required_string(session_id, field_name="session_id")
        user_id = validate_required_string(user_id, field_name="user_id")
        metadata = validate_optional_mapping(metadata, field_name="metadata") or None

        created_at = datetime.now(UTC)

        # Create Session node in MemoryNode with tenant isolation
        attributes = {"user_id": user_id, **(metadata or {})}
        node_sql = """
            INSERT INTO MemoryNode (
                NodeId, TenantId, MemoryTier, Label, LogOddsWeight,
                LastAccessed, Attributes, CreatedAt, UpdatedAt
            ) VALUES (
                @node_id, @tenant_id, @tier, @label, @weight,
                @now, JSON(@attributes), @now, @now
            )
        """

        try:
            database = SpannerClient.get_database()
            with database.batch() as batch:
                batch.execute_update(
                    node_sql,
                    {
                        "node_id": session_id,
                        "tenant_id": tenant_id,
                        "tier": SchemaConfig.MEMORY_TIER_CONTEXT,
                        "label": "Session",
                        "weight": SchemaConfig.INITIAL_WEIGHT,
                        "now": created_at,
                        "attributes": MemoryAPI._serialize_json_attributes(attributes),
                    },
                )

                MemoryAPI._insert_audit_event_in_batch(
                    batch=batch,
                    tenant_id=tenant_id,
                    event_type="CREATE_SESSION",
                    source_node_id=session_id,
                    context={"user_id": user_id},
                    timestamp=created_at,
                )

            return SessionResponse(
                tenant_id=tenant_id,
                session_id=session_id,
                created_at=created_at,
                status="active",
            )
        except Exception as e:
            msg = f"Failed to create session: {e}"
            raise RuntimeError(msg) from e

    @staticmethod
    async def add_semantic_fact(
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        attributes: dict[str, Any] | None = None,
        relationship: dict[str, str] | None = None,
    ) -> FactResponse:
        """Ingest an entity into Semantic Graph with baseline cognitive weight.

        Args:
            tenant_id: Tenant identifier for isolation.
            entity_type: POLE+O entity type (PERSON, OBJECT, etc.)
            entity_id: Unique entity identifier
            attributes: Entity attributes as JSON
            relationship: Optional relationship to existing node (type, source_id)

        Returns:
            FactResponse with entity details

        Raises:
            ValueError: If tenant_id is empty, entity_type is invalid, or entity_id is empty
            RuntimeError: If database write fails
        """
        tenant_id = validate_tenant_id(tenant_id)
        entity_type = validate_entity_type(
            entity_type,
            allowed_entity_types=SchemaConfig.VALID_ENTITY_TYPES,
        )
        entity_id = validate_required_string(entity_id, field_name="entity_id")
        attributes = validate_optional_mapping(attributes, field_name="attributes") or None
        relationship = validate_relationship(relationship)
        if relationship and relationship.get("source_id"):
            source_tier = MemoryAPI._get_node_memory_tier(
                tenant_id,
                relationship["source_id"],
            )
            if source_tier == SchemaConfig.MEMORY_TIER_AUDIT:
                msg = "relationship source cannot be an AUDIT tier node"
                raise ValueError(msg)
            if source_tier is None:
                msg = f"source node {relationship['source_id']} not found in tenant"
                raise ValueError(msg)

        created_at = datetime.now(UTC)
        node_attributes = {
            "entity_type": entity_type,
            **(attributes or {}),
        }

        # Insert entity node with tenant isolation
        node_sql = """
            INSERT INTO MemoryNode (
                NodeId, TenantId, MemoryTier, Label, LogOddsWeight,
                LastAccessed, Attributes, CreatedAt, UpdatedAt
            ) VALUES (
                @node_id, @tenant_id, @tier, @label, @weight,
                @now, JSON(@attributes), @now, @now
            )
        """

        try:
            database = SpannerClient.get_database()
            with database.batch() as batch:
                batch.execute_update(
                    node_sql,
                    {
                        "node_id": entity_id,
                        "tenant_id": tenant_id,
                        "tier": SchemaConfig.MEMORY_TIER_SEMANTIC,
                        "label": entity_type,
                        "weight": SchemaConfig.INITIAL_WEIGHT,
                        "now": created_at,
                        "attributes": MemoryAPI._serialize_json_attributes(node_attributes),
                    },
                )

                # Create relationship if provided
                if relationship:
                    source_id = relationship.get("source_id")
                    rel_type = relationship.get("type", "REFERENCES")
                    if source_id:
                        edge_id = str(uuid.uuid4())
                        edge_sql = """
                            INSERT INTO MemoryEdge (
                                SourceNodeId, TenantId, EdgeId, DestNodeId, RelType,
                                LogOddsWeight, LastAccessed, CreatedAt, UpdatedAt
                            ) VALUES (
                                @source_id, @tenant_id, @edge_id, @dest_id, @rel_type,
                                @weight, @now, @now, @now
                            )
                        """
                        batch.execute_update(
                            edge_sql,
                            {
                                "source_id": source_id,
                                "tenant_id": tenant_id,
                                "edge_id": edge_id,
                                "dest_id": entity_id,
                                "rel_type": rel_type,
                                "weight": SchemaConfig.INITIAL_WEIGHT,
                                "now": created_at,
                            },
                        )

                MemoryAPI._insert_audit_event_in_batch(
                    batch=batch,
                    tenant_id=tenant_id,
                    event_type="ADD_SEMANTIC_FACT",
                    source_node_id=entity_id,
                    context={"entity_type": entity_type, "relationship": relationship},
                    timestamp=created_at,
                )

            # Update weight on successful creation
            await MemoryAPI._update_weight_on_successful_use(
                tenant_id,
                [entity_id],
            )

            return FactResponse(
                tenant_id=tenant_id,
                entity_id=entity_id,
                entity_type=entity_type,
                node_path=f"/{entity_type}/{entity_id}",
                weight=SchemaConfig.INITIAL_WEIGHT,
                created_at=created_at,
            )
        except Exception as e:
            msg = f"Failed to add semantic fact: {e}"
            raise RuntimeError(msg) from e

    @staticmethod
    async def record_audit_event(
        tenant_id: str,
        event_type: str,
        source_node_id: str,
        context: dict[str, Any] | None = None,
    ) -> AuditResponse:
        """Record an immutable audit event in Audit Graph.

        Args:
            tenant_id: Tenant identifier for isolation.
            event_type: Type of audit event
            source_node_id: Node that triggered the event
            context: Event context information

        Returns:
            AuditResponse with event details

        Raises:
            ValueError: If tenant_id, event_type, or source_node_id is empty or invalid
            RuntimeError: If database write fails
        """
        tenant_id = validate_tenant_id(tenant_id)
        event_type = validate_required_string(event_type, field_name="event_type")
        source_node_id = validate_required_string(source_node_id, field_name="source_node_id")
        context = validate_optional_mapping(context, field_name="context") or None

        timestamp = datetime.now(UTC)
        try:
            database = SpannerClient.get_database()
            with database.batch() as batch:
                return MemoryAPI._insert_audit_event_in_batch(
                    batch=batch,
                    tenant_id=tenant_id,
                    event_type=event_type,
                    source_node_id=source_node_id,
                    context=context,
                    timestamp=timestamp,
                )

        except Exception as e:
            msg = f"Failed to record audit event: {e}"
            raise RuntimeError(msg) from e

    @staticmethod
    async def retrieve_context_window(
        tenant_id: str,
        session_id: str,
        window_size: int = 10,
    ) -> ContextResponse:
        """Retrieve recent session history via GQL with edge metadata.

        Args:
            tenant_id: Tenant identifier for isolation.
            session_id: Session identifier
            window_size: Number of turns to retrieve (1-100)

        Returns:
            ContextResponse with context turns

        Raises:
            ValueError: If tenant_id is empty, session_id is empty, or window_size is invalid
            RuntimeError: If database query fails
        """
        tenant_id = validate_tenant_id(tenant_id)
        session_id = validate_required_string(session_id, field_name="session_id")
        window_size = validate_window_size(window_size)

        retrieved_at = datetime.now(UTC)

        # GQL query to retrieve context window with tenant isolation
        # Pattern: (Session)-[HAS_TURN]->(Turn)
        # Ordered by creation timestamp DESC, limited by window_size
        gql_query = """
            MATCH p = (s:Node)-[e]->(t:Node)
            WHERE s.TenantId = @tenant_id
              AND s.NodeId = @session_id
              AND s.MemoryTier = 'CONTEXT'
              AND t.MemoryTier = 'CONTEXT'
            RETURN t.NodeId, t.Label, t.Attributes, t.LogOddsWeight, t.CreatedAt, e.RelType
            ORDER BY t.CreatedAt DESC
            LIMIT @window_size
        """

        try:
            database = SpannerClient.get_database()
            turns = []
            total_weight_sum = 0.0

            with database.snapshot() as snapshot:
                results = snapshot.execute_sql(
                    gql_query,
                    {
                        "tenant_id": tenant_id,
                        "session_id": session_id,
                        "window_size": window_size,
                    },
                )

                for row in results:
                    turn_id, label, attributes, weight, created_at, _rel_type = row
                    turn = ContextTurn(
                        tenant_id=tenant_id,
                        turn_id=turn_id,
                        node_id=turn_id,
                        role=label,
                        content=str(attributes),
                        weight=weight or SchemaConfig.INITIAL_WEIGHT,
                        created_at=created_at,
                    )
                    turns.append(turn)
                    total_weight_sum += turn.weight

            # Log retrieval to audit
            await MemoryAPI.record_audit_event(
                tenant_id,
                "RETRIEVE_CONTEXT_WINDOW",
                session_id,
                {"window_size": window_size, "turns_retrieved": len(turns)},
            )

            # Update weights on successful retrieval
            turn_ids = [turn.turn_id for turn in turns]
            if turn_ids:
                await MemoryAPI._update_weight_on_successful_use(
                    tenant_id,
                    turn_ids,
                    memory_tier=SchemaConfig.MEMORY_TIER_CONTEXT,
                )

            return ContextResponse(
                tenant_id=tenant_id,
                session_id=session_id,
                turns=turns,
                total_weight_sum=total_weight_sum,
                retrieved_at=retrieved_at,
            )
        except Exception as e:
            msg = f"Failed to retrieve context window: {e}"
            raise RuntimeError(msg) from e

    @staticmethod
    async def _update_weight_on_successful_use(
        tenant_id: str,
        node_ids: list[str],
        memory_tier: str = SchemaConfig.MEMORY_TIER_SEMANTIC,
    ) -> None:
        """Update cognitive weights on successful use (confirmation bias).

        Internal method: increments LogOddsWeight by ln(BF) where BF=1.25.

        Args:
            tenant_id: Tenant identifier for isolation.
            node_ids: List of node IDs to update
            memory_tier: Target tier for update.

        Raises:
            ValueError: If tenant_id is empty, memory_tier is invalid, or tier is immutable.
            RuntimeError: If update fails
        """
        tenant_id = validate_tenant_id(tenant_id)
        if not node_ids:
            return

        node_ids = [validate_required_string(node_id, field_name="node_id") for node_id in node_ids]

        if memory_tier not in SchemaConfig.VALID_MEMORY_TIERS:
            msg = f"invalid memory_tier. Must be one of: {SchemaConfig.VALID_MEMORY_TIERS}"
            raise ValueError(msg)

        if memory_tier == SchemaConfig.MEMORY_TIER_AUDIT:
            try:
                MemoryAPI._enforce_audit_append_only("UPDATE")
            except PermissionError:
                # Keep MemoryAPI contract stable while still enforcing append-only checks.
                logger.warning("audit immutability guard triggered for audit tier update")
            msg = "audit tier is append-only and cannot be updated"
            raise ValueError(msg)

        # Bayesian log-odds update: ln(1.25) ≈ 0.223
        bayes_factor_ln = math.log(SchemaConfig.BAYES_FACTOR_SUCCESS)

        sql = """
            UPDATE MemoryNode
            SET LogOddsWeight = LogOddsWeight + @delta,
                LastAccessed = CURRENT_TIMESTAMP(),
                UpdatedAt = CURRENT_TIMESTAMP()
            WHERE TenantId = @tenant_id
              AND NodeId IN UNNEST(@node_ids)
              AND MemoryTier = @tier
        """

        try:
            database = SpannerClient.get_database()
            with database.batch() as batch:
                batch.execute_update(
                    sql,
                    {
                        "tenant_id": tenant_id,
                        "delta": bayes_factor_ln,
                        "node_ids": node_ids,
                        "tier": memory_tier,
                    },
                )
        except Exception as e:  # noqa: BLE001
            # Log but don't raise - weight update is not critical to operation
            logger.warning("failed to update weights for tenant %s", tenant_id, exc_info=e)
