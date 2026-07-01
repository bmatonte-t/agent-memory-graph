"""Evidence metadata contracts for Phase 4 MindMap integration.

This module defines the typed contracts for evidence provenance, sufficiency
signals, and audit linkage that extend Phase 3 ABAC authorization.

Entities defined here are NOT persisted as full objects in Spanner;
instead they structure the evidence context passed through the MindMap
synthesis pipeline and link to ENGRAM_EVIDENCE nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceSourceType(StrEnum):
    """Classification of evidence retrieval strategy."""

    PATH_BASED = "path_based"
    """Evidence retrieved via graph shortest-path traversal (Phase 4B)."""

    NEIGHBOR_BASED = "neighbor_based"
    """Evidence retrieved via bounded neighbor enrichment (Phase 4C)."""

    HYBRID = "hybrid"
    """Evidence combines multiple retrieval strategies."""

    UNKNOWN = "unknown"
    """Source type unclassified or unavailable."""


class EvidenceInsufficientReason(StrEnum):
    """Enumeration of reasons evidence retrieval may be insufficient."""

    NO_PATHS_FOUND = "no_paths_found"
    """Graph path search returned no results."""

    NO_NEIGHBORS_FOUND = "no_neighbors_found"
    """Entity has no outgoing relationships."""

    TOKEN_BUDGET_EXCEEDED = "token_budget_exceeded"  # noqa: S105
    """Evidence exceeded maximum token allocation."""

    AUTHORIZATION_DENIED = "authorization_denied"
    """ABAC scope prevented access to relevant evidence."""

    TIMEOUT = "timeout"
    """Evidence retrieval exceeded maximum latency threshold."""

    EMPTY_GRAPH = "empty_graph"
    """Graph contains no data for tenant."""

    UNKNOWN = "unknown"
    """Insufficient evidence reason not determined."""


class ContradictionSeverity(StrEnum):
    """Severity level for a contradiction flag on an evidence item."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class ContradictionFlag:
    """Typed representation of a contradiction flag attached to an evidence item.

    Replaces the fragile ``"SEVERITY:node_id"`` string format with a validated
    dataclass that handles node IDs containing colons.
    """

    severity: ContradictionSeverity
    node_id: str

    @classmethod
    def from_string(cls, flag_str: str) -> "ContradictionFlag":
        """Parse legacy ``'SEVERITY:node_id'`` format with validation.

        Args:
            flag_str: Raw contradiction flag string (e.g. ``"HIGH:node-123"``).

        Returns:
            Parsed :class:`ContradictionFlag` instance.

        Raises:
            ValueError: If the format is invalid, severity is unknown, or
                node_id is empty.
        """
        parts = flag_str.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid contradiction flag format: {flag_str!r}")
        severity_str, node_id = parts
        if not node_id:
            raise ValueError(f"node_id cannot be empty in contradiction flag: {flag_str!r}")
        return cls(severity=ContradictionSeverity(severity_str.upper()), node_id=node_id)


class EvidenceItem(BaseModel):
    """Single evidence element returned from retrieval pipeline.

    This represents evidence in its serialized, compact form (not raw
    graph nodes/edges). The EvidenceItem is created by Phase 4B/4C
    retrieval stages and tracked in ENGRAM_EVIDENCE.

    Phase 5: Extends with source-aware confidence, freshness, and contradiction metadata.
    """

    evidence_id: str = Field(..., min_length=1, description="Unique identifier (UUID format).")
    source_type: EvidenceSourceType = Field(
        ..., description="Retrieval strategy used to obtain this evidence."
    )
    evidence_number: int = Field(..., ge=1, description="Sequential index (1-based).")
    graph_path: str = Field(
        ..., min_length=1, description="Compact path format: 'entity->rel->entity->...'"
    )
    serialized_form: str | None = Field(
        default=None, description="Natural language evidence (LLM-generated)."
    )
    access_timestamp: datetime = Field(..., description="When evidence was retrieved.")
    cognitive_weight: float = Field(
        default=1.0, ge=0.0, le=10.0, description="Weight for Phase 5 gating."
    )
    audit_log_ref: str | None = Field(default=None, description="Reference to AUDIT_EVENTS entry.")
    # Phase 5: Confidence metadata
    source_agent_id: str | None = Field(
        default=None, description="Agent that created this evidence (Phase 5)."
    )
    source_confidence_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Source-aware confidence (0.0-1.0, Phase 5)."
    )
    freshness_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Computed freshness decay score (0.0-1.0, Phase 5).",
    )
    contradiction_flags: list[str] = Field(
        default_factory=list, description="Detected contradictions with other nodes (Phase 5)."
    )


class EvidenceContext(BaseModel):
    """Complete evidence context for a synthesis request.

    This is the structured representation passed from retrieval stages
    to synthesis stages, enabling explicit grounding signals.

    If is_empty = True, the synthesis stage should add caveats to the
    prompt to avoid hallucination.
    """

    items: list[EvidenceItem] = Field(
        default_factory=list, description="All evidence items retrieved."
    )
    total_items: int = Field(default=0, description="Count of evidence items.")
    total_chars: int = Field(default=0, description="Total character count (for token tracking).")
    path_count: int = Field(default=0, description="Count of path-based items.")
    neighbor_count: int = Field(default=0, description="Count of neighbor-based items.")
    is_empty: bool = Field(default=False, description="True if no evidence retrieved.")
    is_sufficient: bool = Field(
        default=False,
        description=(
            "True if evidence meets sufficiency heuristic: "
            "(paths>=1 AND neighbors>=1) OR (either>=3)."
        ),
    )
    insufficient_reasons: list[EvidenceInsufficientReason] = Field(
        default_factory=list, description="Reasons evidence was insufficient."
    )
    retrieval_latency_ms: float = Field(
        default=0.0, ge=0.0, description="Total retrieval stage latency."
    )


class EvidenceSummary(BaseModel):
    """Summary of evidence availability for synthesis response.

    This is returned in MindMapResponse to signal to clients what
    evidence grounded the synthesis.

    Phase 5: Extends with confidence breakdown and contradiction signals.
    """

    total_items: int = Field(default=0, description="Count of evidence items.")
    path_count: int = Field(default=0, description="Count of path-based items.")
    neighbor_count: int = Field(default=0, description="Count of neighbor-based items.")
    is_sufficient: bool = Field(
        default=False, description="Whether evidence meets sufficiency heuristic."
    )
    is_empty: bool = Field(default=False, description="Whether no evidence available.")
    insufficient_reasons: list[EvidenceInsufficientReason] = Field(
        default_factory=list, description="Reasons evidence was insufficient (if any)."
    )
    retrieval_latency_ms: float = Field(
        default=0.0, ge=0.0, description="Evidence retrieval latency."
    )
    # Phase 5: Confidence and contradiction metadata
    min_confidence_in_set: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Minimum source confidence across all items (Phase 5).",
    )
    average_freshness: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Average freshness score across all items (Phase 5).",
    )
    contradiction_warnings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Aggregated contradictions detected (Phase 5); format: "
        "[{'conflicting_count': int, 'severity': str, 'nodes': [str]}]",
    )
