"""Core memory API implementations."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.db.schema import SchemaConfig
from src.db.spanner_client import SpannerClient
from src.models.schemas import (
    AuditResponse,
    ContextResponse,
    ContextTurn,
    FactResponse,
    SessionResponse,
)


class MemoryAPI:
    """Core memory API for tripartite memory operations."""

    @staticmethod
    async def create_session(
        session_id: str, user_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> SessionResponse:
        """
        Create a new session and initialize Context Graph.

        Args:
            session_id: Unique session identifier
            user_id: User ID associated with session
            metadata: Optional session metadata

        Returns:
            SessionResponse with session details

        Raises:
            ValueError: If session_id is empty or invalid
            RuntimeError: If database write fails
        """
        if not session_id or not user_id:
            raise ValueError("session_id and user_id cannot be empty")

        created_at = datetime.utcnow()

        # Create Session node in MemoryNode
        attributes = {"user_id": user_id, **(metadata or {})}
        node_sql = """
            INSERT INTO MemoryNode (
                NodeId, MemoryTier, Label, LogOddsWeight, 
                LastAccessed, Attributes, CreatedAt, UpdatedAt
            ) VALUES (
                @node_id, @tier, @label, @weight, 
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
                        "tier": SchemaConfig.MEMORY_TIER_CONTEXT,
                        "label": "Session",
                        "weight": SchemaConfig.INITIAL_WEIGHT,
                        "now": created_at,
                        "attributes": str(attributes),
                    },
                )

            # Log audit event
            await MemoryAPI.record_audit_event(
                "CREATE_SESSION", session_id, {"user_id": user_id}
            )

            return SessionResponse(
                session_id=session_id,
                created_at=created_at,
                status="active",
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create session: {e}")

    @staticmethod
    async def add_semantic_fact(
        entity_type: str,
        entity_id: str,
        attributes: Optional[Dict[str, Any]] = None,
        relationship: Optional[Dict[str, str]] = None,
    ) -> FactResponse:
        """
        Ingest an entity into Semantic Graph with baseline cognitive weight.

        Args:
            entity_type: POLE+O entity type (PERSON, OBJECT, etc.)
            entity_id: Unique entity identifier
            attributes: Entity attributes as JSON
            relationship: Optional relationship to existing node (type, source_id)

        Returns:
            FactResponse with entity details

        Raises:
            ValueError: If entity_type is invalid or entity_id is empty
            RuntimeError: If database write fails
        """
        if entity_type not in SchemaConfig.VALID_ENTITY_TYPES:
            raise ValueError(
                f"Invalid entity_type. Must be one of: {SchemaConfig.VALID_ENTITY_TYPES}"
            )
        if not entity_id:
            raise ValueError("entity_id cannot be empty")

        created_at = datetime.utcnow()
        node_attributes = {
            "entity_type": entity_type,
            **(attributes or {}),
        }

        # Insert entity node
        node_sql = """
            INSERT INTO MemoryNode (
                NodeId, MemoryTier, Label, LogOddsWeight,
                LastAccessed, Attributes, CreatedAt, UpdatedAt
            ) VALUES (
                @node_id, @tier, @label, @weight,
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
                        "tier": SchemaConfig.MEMORY_TIER_SEMANTIC,
                        "label": entity_type,
                        "weight": SchemaConfig.INITIAL_WEIGHT,
                        "now": created_at,
                        "attributes": str(node_attributes),
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
                                SourceNodeId, EdgeId, DestNodeId, RelType,
                                LogOddsWeight, LastAccessed, CreatedAt, UpdatedAt
                            ) VALUES (
                                @source_id, @edge_id, @dest_id, @rel_type,
                                @weight, @now, @now, @now
                            )
                        """
                        batch.execute_update(
                            edge_sql,
                            {
                                "source_id": source_id,
                                "edge_id": edge_id,
                                "dest_id": entity_id,
                                "rel_type": rel_type,
                                "weight": SchemaConfig.INITIAL_WEIGHT,
                                "now": created_at,
                            },
                        )

            # Log audit event
            await MemoryAPI.record_audit_event(
                "ADD_SEMANTIC_FACT",
                entity_id,
                {"entity_type": entity_type, "relationship": relationship},
            )

            # Update weight on successful creation
            await MemoryAPI._update_weight_on_successful_use([entity_id])

            return FactResponse(
                entity_id=entity_id,
                entity_type=entity_type,
                node_path=f"/{entity_type}/{entity_id}",
                weight=SchemaConfig.INITIAL_WEIGHT,
                created_at=created_at,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to add semantic fact: {e}")

    @staticmethod
    async def record_audit_event(
        event_type: str,
        source_node_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AuditResponse:
        """
        Record an immutable audit event in Audit Graph.

        Args:
            event_type: Type of audit event
            source_node_id: Node that triggered the event
            context: Event context information

        Returns:
            AuditResponse with event details

        Raises:
            ValueError: If event_type or source_node_id is empty
            RuntimeError: If database write fails
        """
        if not event_type or not source_node_id:
            raise ValueError("event_type and source_node_id cannot be empty")

        timestamp = datetime.utcnow()
        event_id = str(uuid.uuid4())
        event_attributes = {
            "event_type": event_type,
            "source_node_id": source_node_id,
            **(context or {}),
        }

        # Insert audit event node (append-only)
        sql = """
            INSERT INTO MemoryNode (
                NodeId, MemoryTier, Label, LogOddsWeight,
                LastAccessed, Attributes, CreatedAt, UpdatedAt
            ) VALUES (
                @node_id, @tier, @label, @weight,
                @now, JSON(@attributes), @now, @now
            )
        """

        try:
            database = SpannerClient.get_database()
            with database.batch() as batch:
                batch.execute_update(
                    sql,
                    {
                        "node_id": event_id,
                        "tier": SchemaConfig.MEMORY_TIER_AUDIT,
                        "label": "Event",
                        "weight": SchemaConfig.INITIAL_WEIGHT,
                        "now": timestamp,
                        "attributes": str(event_attributes),
                    },
                )

            return AuditResponse(
                event_id=event_id,
                event_type=event_type,
                timestamp=timestamp,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to record audit event: {e}")

    @staticmethod
    async def retrieve_context_window(
        session_id: str, window_size: int = 10
    ) -> ContextResponse:
        """
        Retrieve recent session history via GQL with edge metadata.

        Args:
            session_id: Session identifier
            window_size: Number of turns to retrieve (1-100)

        Returns:
            ContextResponse with context turns

        Raises:
            ValueError: If session_id is empty or window_size is invalid
            RuntimeError: If database query fails
        """
        if not session_id:
            raise ValueError("session_id cannot be empty")
        if not (1 <= window_size <= 100):
            raise ValueError("window_size must be between 1 and 100")

        retrieved_at = datetime.utcnow()

        # GQL query to retrieve context window
        # Pattern: (Session)-[HAS_TURN]->(Turn)
        # Ordered by creation timestamp DESC, limited by window_size
        gql_query = """
            MATCH p = (s:Node)-[e]->(t:Node)
            WHERE s.NodeId = @session_id 
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
                        "session_id": session_id,
                        "window_size": window_size,
                    },
                )

                for row in results:
                    turn_id, label, attributes, weight, created_at, rel_type = row
                    turn = ContextTurn(
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
                "RETRIEVE_CONTEXT_WINDOW",
                session_id,
                {"window_size": window_size, "turns_retrieved": len(turns)},
            )

            # Update weights on successful retrieval
            turn_ids = [turn.turn_id for turn in turns]
            if turn_ids:
                await MemoryAPI._update_weight_on_successful_use(turn_ids)

            return ContextResponse(
                session_id=session_id,
                turns=turns,
                total_weight_sum=total_weight_sum,
                retrieved_at=retrieved_at,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve context window: {e}")

    @staticmethod
    async def _update_weight_on_successful_use(node_ids: List[str]) -> None:
        """
        Update cognitive weights on successful use (confirmation bias).

        Internal method: increments LogOddsWeight by ln(BF) where BF=1.25.

        Args:
            node_ids: List of node IDs to update

        Raises:
            RuntimeError: If update fails
        """
        if not node_ids:
            return

        # Bayesian log-odds update: ln(1.25) ≈ 0.223
        bayes_factor_ln = import_math().log(SchemaConfig.BAYES_FACTOR_SUCCESS)

        sql = """
            UPDATE MemoryNode
            SET LogOddsWeight = LogOddsWeight + @delta,
                LastAccessed = CURRENT_TIMESTAMP(),
                UpdatedAt = CURRENT_TIMESTAMP()
            WHERE NodeId IN UNNEST(@node_ids)
              AND MemoryTier = @tier
        """

        try:
            database = SpannerClient.get_database()
            with database.batch() as batch:
                batch.execute_update(
                    sql,
                    {
                        "delta": bayes_factor_ln,
                        "node_ids": node_ids,
                        "tier": SchemaConfig.MEMORY_TIER_SEMANTIC,
                    },
                )
        except Exception as e:
            # Log but don't raise - weight update is not critical to operation
            print(f"Warning: Failed to update weights: {e}")


def import_math():
    """Helper to import math module (avoids circular imports)."""
    import math

    return math
