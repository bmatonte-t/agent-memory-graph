"""Pydantic models for API request/response schemas."""

from datetime import datetime  # noqa: TC003
from typing import Any

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    """Response model for create_session operation."""

    session_id: str = Field(..., description="Unique session identifier")
    created_at: datetime = Field(..., description="Session creation timestamp")
    status: str = Field(default="active", description="Session status")


class FactResponse(BaseModel):
    """Response model for add_semantic_fact operation."""

    entity_id: str = Field(..., description="Unique entity identifier")
    entity_type: str = Field(
        ..., description="POLE+O entity type (PERSON, OBJECT, LOCATION, EVENT, ORGANIZATION)"
    )
    node_path: str = Field(..., description="Spanner node path")
    weight: float = Field(default=0.5, description="Initial cognitive weight")
    created_at: datetime = Field(..., description="Entity creation timestamp")


class AuditResponse(BaseModel):
    """Response model for record_audit_event operation."""

    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Type of audit event")
    timestamp: datetime = Field(..., description="Event timestamp")


class ContextTurn(BaseModel):
    """Represents a single turn in conversation context."""

    turn_id: str = Field(..., description="Turn identifier")
    node_id: str = Field(..., description="Spanner node ID")
    role: str = Field(..., description="Role (user, agent, system)")
    content: str = Field(..., description="Turn content")
    weight: float = Field(default=0.5, description="Cognitive weight")
    created_at: datetime = Field(..., description="Turn creation timestamp")


class ContextResponse(BaseModel):
    """Response model for retrieve_context_window operation."""

    session_id: str = Field(..., description="Session identifier")
    turns: list[ContextTurn] = Field(default_factory=list, description="Context turns")
    total_weight_sum: float = Field(default=0.0, description="Sum of all turn weights")
    retrieved_at: datetime = Field(..., description="Retrieval timestamp")


class AddSemanticFactRequest(BaseModel):
    """Request model for add_semantic_fact operation."""

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
    user_id: str = Field(..., description="User ID associated with session")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Session metadata")


class RecordAuditEventRequest(BaseModel):
    """Request model for record_audit_event operation."""

    event_type: str = Field(..., description="Type of audit event")
    source_node_id: str = Field(..., description="Source node ID triggering event")
    context: dict[str, Any] = Field(default_factory=dict, description="Event context information")


class RetrieveContextWindowRequest(BaseModel):
    """Request model for retrieve_context_window operation."""

    session_id: str = Field(..., description="Session identifier")
    window_size: int = Field(default=10, ge=1, le=100, description="Number of turns to retrieve")


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
