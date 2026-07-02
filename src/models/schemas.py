"""Pydantic models for API request/response schemas."""

from datetime import datetime  # noqa: TC003
from typing import Any

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    """Response model for create_session operation."""

    session_id: str = Field(..., description="Unique session identifier")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    created_at: datetime = Field(..., description="Session creation timestamp")
    status: str = Field(default="active", description="Session status")


class SessionKnowledgeExtractionResponse(BaseModel):
    """Response model for extracted knowledge generated from a closed session."""

    session_id: str = Field(..., description="Session identifier")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    domain: str = Field(..., description="Resolved semantic domain for extracted knowledge")
    processed_turns: int = Field(..., ge=0, description="Total context turns processed")
    extracted_facts: int = Field(..., ge=0, description="Semantic facts created")
    skipped_facts: int = Field(..., ge=0, description="Facts skipped due to deduplication")
    failed_facts: int = Field(..., ge=0, description="Facts that failed to persist")
    extracted_at: datetime = Field(..., description="Extraction completion timestamp")


class EndSessionResponse(BaseModel):
    """Response model for session closure and extraction protocol."""

    session_id: str = Field(..., description="Session identifier")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    status: str = Field(default="closed", description="Session status after closure")
    end_reason: str = Field(..., description="Reason for session closure")
    ended_at: datetime = Field(..., description="Session closure timestamp")
    extraction_status: str = Field(..., description="Extraction protocol final status")
    extraction: SessionKnowledgeExtractionResponse = Field(
        ..., description="Extraction summary for semantic persistence"
    )


class FactResponse(BaseModel):
    """Response model for add_semantic_fact operation.

    Phase 5: Extends with confidence and contradiction metadata.
    """

    entity_id: str = Field(..., description="Unique entity identifier")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    entity_type: str = Field(
        ..., description="POLE+O entity type (PERSON, OBJECT, LOCATION, EVENT, ORGANIZATION)"
    )
    node_path: str = Field(..., description="Spanner node path")
    weight: float = Field(default=0.5, description="Initial cognitive weight")
    created_at: datetime = Field(..., description="Entity creation timestamp")
    # Phase 5: Confidence and contradiction metadata
    source_confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Initial confidence score based on source type (Phase 5).",
    )
    detected_contradictions: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Contradictions detected during ingestion (Phase 5); "
            "format: [{'severity': str, 'conflicting_nodes': [str], 'reason': str}]"
        ),
    )
    source_agent_id: str | None = Field(
        default=None, description="Agent that created this fact (Phase 5)."
    )
    source_query_id: str | None = Field(
        default=None, description="Query ID that created this fact (Phase 5)."
    )


class AuditResponse(BaseModel):
    """Response model for record_audit_event operation."""

    event_id: str = Field(..., description="Unique event identifier")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    event_type: str = Field(..., description="Type of audit event")
    timestamp: datetime = Field(..., description="Event timestamp")


class ContextTurn(BaseModel):
    """Represents a single turn in conversation context."""

    turn_id: str = Field(..., description="Turn identifier")
    node_id: str = Field(..., description="Spanner node ID")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    role: str = Field(..., description="Role (user, agent, system)")
    content: str = Field(..., description="Turn content")
    weight: float = Field(default=0.5, description="Cognitive weight")
    created_at: datetime = Field(..., description="Turn creation timestamp")


class ContextResponse(BaseModel):
    """Response model for retrieve_context_window operation."""

    session_id: str = Field(..., description="Session identifier")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    turns: list[ContextTurn] = Field(default_factory=list, description="Context turns")
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for next page retrieval, or null when exhausted",
    )
    has_more: bool = Field(default=False, description="Whether additional context turns exist")
    total_weight_sum: float = Field(default=0.0, description="Sum of all turn weights")
    retrieved_at: datetime = Field(..., description="Retrieval timestamp")


class AddSemanticFactRequest(BaseModel):
    """Request model for add_semantic_fact operation."""

    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    entity_type: str = Field(
        ...,
        description="POLE+O entity type: PERSON, OBJECT, LOCATION, EVENT, or ORGANIZATION",
    )
    entity_id: str = Field(..., description="Unique entity identifier")
    attributes: dict[str, Any] = Field(
        default_factory=dict, description="Entity attributes as JSON"
    )
    relationship: dict[str, str] | None = Field(
        None, description="Optional relationship to existing node (type, source_id)"
    )


class CreateSessionRequest(BaseModel):
    """Request model for create_session operation."""

    session_id: str = Field(..., description="Unique session identifier")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    user_id: str = Field(..., description="User ID associated with session")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Session metadata")


class RecordAuditEventRequest(BaseModel):
    """Request model for record_audit_event operation."""

    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    event_type: str = Field(..., description="Type of audit event")
    source_node_id: str = Field(..., description="Source node ID triggering event")
    context: dict[str, Any] = Field(default_factory=dict, description="Event context information")


class RetrieveContextWindowRequest(BaseModel):
    """Request model for retrieve_context_window operation."""

    session_id: str = Field(..., description="Session identifier")
    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    window_size: int = Field(default=10, ge=1, le=100, description="Number of turns to retrieve")
    cursor: str | None = Field(
        default=None,
        description="Opaque cursor from previous context retrieval page",
    )


class EndSessionRequest(BaseModel):
    """Request model for ending a session and extracting knowledge."""

    tenant_id: str = Field(..., description="Tenant identifier for multi-tenant isolation")
    session_id: str = Field(..., description="Session identifier")
    end_reason: str = Field(
        default="completed",
        description="Session end reason: completed, timeout, or aborted",
    )
    domain_hint: str | None = Field(
        default=None,
        description="Optional target semantic domain for extracted knowledge",
    )
    window_size: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Number of context turns to scan for extraction",
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    timestamp: datetime = Field(..., description="Error timestamp")


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Check timestamp")
    database: str = Field(..., description="Database connection status")


class GraphExportNode(BaseModel):
    """JSON-LD node representation for graph exports."""

    id: str = Field(..., serialization_alias="@id", description="JSON-LD node identifier")
    type: str = Field(..., serialization_alias="@type", description="JSON-LD node type")
    tenant_id: str = Field(..., description="Tenant identifier")
    memory_tier: str = Field(..., description="Memory tier for this node")
    label: str = Field(..., description="Domain label for the node")
    weight: float = Field(..., description="Current node weight")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Node attributes payload")


class GraphExportEdge(BaseModel):
    """JSON-LD edge representation for graph exports."""

    id: str = Field(..., serialization_alias="@id", description="JSON-LD edge identifier")
    type: str = Field(
        default="MemoryEdge",
        serialization_alias="@type",
        description="JSON-LD edge type",
    )
    tenant_id: str = Field(..., description="Tenant identifier")
    relationship_type: str = Field(..., description="Relationship type")
    source_node_id: str = Field(..., description="Source node identifier")
    destination_node_id: str = Field(..., description="Destination node identifier")
    weight: float = Field(..., description="Current edge weight")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Edge attributes payload")


class GraphExportResponse(BaseModel):
    """JSON-LD export envelope for tenant graph snapshots."""

    context: dict[str, str] = Field(
        default_factory=dict,
        serialization_alias="@context",
        description="JSON-LD context map",
    )
    graph: list[GraphExportNode | GraphExportEdge] = Field(
        default_factory=list,
        serialization_alias="@graph",
        description="JSON-LD graph entries",
    )
    tenant_id: str = Field(..., description="Tenant identifier")
    node_count: int = Field(..., ge=0, description="Exported node count")
    edge_count: int = Field(..., ge=0, description="Exported edge count")
    exported_at: datetime = Field(..., description="Export timestamp")
