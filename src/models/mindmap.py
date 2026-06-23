"""Typed contracts for the MindMap query pipeline."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.models.confidence import SynthesisConfidenceSignal
    from src.models.evidence import EvidenceSummary


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
    """Canonical fact generated from graph evidence.

    Phase 5: Extends with source confidence, freshness, and contradiction signals.
    """

    fact_id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    path_id: str = Field(..., min_length=1)
    edge_ids: list[str] = Field(default_factory=list)
    rel_type: str = Field(..., min_length=1)
    weight: float = Field(...)
    # Phase 5: Confidence metadata
    source_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Source confidence score for this fact (Phase 5).",
    )
    freshness_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Freshness score (0.0-1.0) indicating fact recency (Phase 5).",
    )
    contradiction_flags: list[str] = Field(
        default_factory=list, description="Contradictions detected with other facts (Phase 5)."
    )


class SerializationResult(BaseModel):
    """Machine and human readable evidence payload."""

    facts: list[SerializedFact] = Field(default_factory=list)
    markdown: str = Field(default="")
    latency_ms: float = Field(..., ge=0.0)


class SynthesisResult(BaseModel):
    """Final response constrained to serialized evidence.

    Phase 5: Extends with confidence signals and contradiction warnings.
    """

    response_text: str = Field(..., min_length=1)
    claim_fact_ids: list[str] = Field(default_factory=list)
    grounded: bool = Field(...)
    latency_ms: float = Field(..., ge=0.0)
    # Phase 5: Confidence signals
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence of synthesis response (Phase 5).",
    )
    contradiction_warnings: list[dict[str, object]] = Field(
        default_factory=list,
        description="Contradictions detected in evidence (Phase 5); "
        "format: [{'severity': str, 'count': int, 'node_ids': [str]}]",
    )
    confidence_signal: SynthesisConfidenceSignal | None = Field(
        default=None,
        description="Detailed Phase 5 confidence and contradiction signal bundle.",
    )


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
    """Pipeline execution response payload.

    Includes evidence metadata (Phase 4) to signal grounding quality to clients.
    """

    query: str = Field(..., min_length=1)
    synthesis: SynthesisResult
    trace: MindMapTrace
    evidence_summary: EvidenceSummary | None = Field(
        default=None,
        description=(
            "Evidence summary for Phase 4: counts, sufficiency signal, "
            "and insufficient reasons if applicable."
        ),
    )


def _rebuild_models() -> None:
    """Rebuild Pydantic models with explicit forward reference namespace."""
    from src.models.confidence import SynthesisConfidenceSignal  # noqa: PLC0415
    from src.models.evidence import EvidenceSummary  # noqa: PLC0415

    forward_ref_types = {
        "SynthesisConfidenceSignal": SynthesisConfidenceSignal,
        "EvidenceSummary": EvidenceSummary,
    }
    SynthesisResult.model_rebuild(_types_namespace=forward_ref_types)
    MindMapResponse.model_rebuild(_types_namespace=forward_ref_types)


_rebuild_models()
