"""Typed contracts for the MindMap query pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class PipelineStage(StrEnum):
    """Ordered MindMap pipeline stages."""

    MINE = "mine"
    AGGREGATE = "aggregate"
    SERIALIZE = "serialize"
    SYNTHESIZE = "synthesize"


class PipelineErrorCode(StrEnum):
    """Stable stage error taxonomy for Phase 2."""

    VALIDATION_ERROR = "validation_error"
    MODEL_ERROR = "model_error"
    RETRIEVAL_ERROR = "retrieval_error"
    GROUNDING_ERROR = "grounding_error"
    TIMEOUT_ERROR = "timeout_error"


class MinedEntity(BaseModel):
    """Entity extracted from user input."""

    entity_id: str = Field(..., min_length=1)
    entity_type: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


class MiningResult(BaseModel):
    """Structured result produced by the mining stage."""

    intent: str = Field(..., min_length=1)
    entities: list[MinedEntity] = Field(default_factory=list)
    latency_ms: float = Field(..., ge=0.0)


class EvidenceNode(BaseModel):
    """Evidence node returned by graph aggregation."""

    node_id: str = Field(..., min_length=1)
    memory_tier: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    weight: float = Field(...)


class EvidenceEdge(BaseModel):
    """Evidence edge returned by graph aggregation."""

    edge_id: str = Field(..., min_length=1)
    source_node_id: str = Field(..., min_length=1)
    destination_node_id: str = Field(..., min_length=1)
    rel_type: str = Field(..., min_length=1)
    weight: float = Field(...)


class EvidencePath(BaseModel):
    """Single path proving relationship traversal in aggregation."""

    path_id: str = Field(..., min_length=1)
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)


class AggregationResult(BaseModel):
    """Graph retrieval output including provenance metadata."""

    nodes: list[EvidenceNode] = Field(default_factory=list)
    edges: list[EvidenceEdge] = Field(default_factory=list)
    paths: list[EvidencePath] = Field(default_factory=list)
    latency_ms: float = Field(..., ge=0.0)


class SerializedFact(BaseModel):
    """Canonical fact generated from graph evidence."""

    fact_id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    path_id: str = Field(..., min_length=1)
    edge_ids: list[str] = Field(default_factory=list)


class SerializationResult(BaseModel):
    """Machine and human readable evidence payload."""

    facts: list[SerializedFact] = Field(default_factory=list)
    markdown: str = Field(default="")
    latency_ms: float = Field(..., ge=0.0)


class SynthesisResult(BaseModel):
    """Final response constrained to serialized evidence."""

    response_text: str = Field(..., min_length=1)
    claim_fact_ids: list[str] = Field(default_factory=list)
    grounded: bool = Field(...)
    latency_ms: float = Field(..., ge=0.0)


class StageTiming(BaseModel):
    """Observed latency for a specific stage."""

    stage: PipelineStage
    latency_ms: float = Field(..., ge=0.0)


class MindMapTrace(BaseModel):
    """Traceability envelope linking all pipeline artifacts."""

    trace_id: str = Field(..., min_length=1)
    mined_entities: list[str] = Field(default_factory=list)
    path_ids: list[str] = Field(default_factory=list)
    fact_ids: list[str] = Field(default_factory=list)
    stage_timings: list[StageTiming] = Field(default_factory=list)
    created_at: datetime


class MindMapRequest(BaseModel):
    """Pipeline execution request payload."""

    query: str = Field(..., min_length=1)
    session_id: str | None = Field(default=None)


class MindMapResponse(BaseModel):
    """Pipeline execution response payload."""

    query: str = Field(..., min_length=1)
    synthesis: SynthesisResult
    trace: MindMapTrace
