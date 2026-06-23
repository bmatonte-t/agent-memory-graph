"""Confidence quality metadata contracts for Phase 5 Engram integration.

This module defines typed contracts for source-aware confidence, freshness decay,
contradiction detection, and synthesis-level confidence signals that extend Phase 4
evidence grounding.

Entities defined here are used to:
1. Track source confidence at evidence retrieval time
2. Compute freshness scores based on access timestamps
3. Detect contradictions between facts
4. Gate LLM synthesis on confidence thresholds
5. Return confidence signals in MindMapResponse for client awareness
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

CONFIDENCE_LOWER_BOUND = 0.0
CONFIDENCE_BUCKET_LOW_UPPER_BOUND = 0.3
CONFIDENCE_BUCKET_MEDIUM_UPPER_BOUND = 0.6
CONFIDENCE_BUCKET_HIGH_UPPER_BOUND = 0.8
CONFIDENCE_UPPER_BOUND = 1.0
MAX_FRESHNESS_AGE_HOURS = 100.0
LOW_CONFIDENCE_THRESHOLD = 0.3


class SourceType(StrEnum):
    """Classification of fact source and initial confidence."""

    USER_PROVIDED = "user_provided"
    """Fact provided directly by user query. Confidence: 1.0 (high trust)."""

    API_DERIVED = "api_derived"
    """Fact inferred from API results or external systems. Confidence: 0.7 (moderate trust)."""

    INFERRED = "inferred"
    """Fact derived from graph relationships. Confidence: 0.5 (lower trust)."""

    UNKNOWN = "unknown"
    """Source type unclassified. Confidence: 0.5 (conservative default)."""


class ContradictionSeverity(StrEnum):
    """Severity level of detected contradiction."""

    LOW = "low"
    """Minor semantic differences; both facts may be true in different contexts."""

    MEDIUM = "medium"
    """Direct conflict; one fact contradicts the other."""

    HIGH = "high"
    """Explicit contradiction marker or temporal impossibility detected."""


class SourceConfidence(BaseModel):
    """Source-aware confidence score for a fact or evidence item."""

    source_type: SourceType = Field(
        ..., description="Classification of fact origin (user, API, inferred)."
    )
    initial_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score at ingest (0.0-1.0)."
    )
    confidence_factors: list[str] = Field(
        default_factory=list,
        description="Factors influencing confidence (e.g., 'multiple_sources', 'recent_update').",
    )

    def adjust_score(self, adjustment: float) -> float:
        """Apply adjustment to confidence score, bounded to [0.0, 1.0].

        Args:
            adjustment: Amount to add to score (can be negative).

        Returns:
            Adjusted confidence score, clamped to valid range.
        """
        return max(0.0, min(1.0, self.initial_score + adjustment))


class FreshnessScore(BaseModel):
    """Computed freshness score based on temporal decay.

    Freshness decays exponentially: freshness = exp(-λ * hours_old)
    At λ=0.1 (default): 50% freshness at ~7 hours, 25% at ~14 hours.
    """

    hours_old: float = Field(..., ge=0.0, description="Time elapsed since last access (hours).")
    decay_factor: float = Field(
        ..., ge=0.0, le=1.0, description="Decay parameter (λ); default 0.1."
    )
    current_score: float = Field(
        ..., ge=0.0, le=1.0, description="Computed freshness score (0.0-1.0)."
    )
    gated: bool = Field(
        default=False,
        description="Whether fact failed freshness threshold and should be filtered.",
    )

    @staticmethod
    def compute(access_timestamp: datetime, decay_lambda: float = 0.1) -> FreshnessScore:
        """Compute freshness score for a given access timestamp.

        Args:
            access_timestamp: Timestamp when evidence was last accessed.
            decay_lambda: Decay rate (default 0.1). Higher = faster decay.

        Returns:
            FreshnessScore with computed score and gating decision.
        """
        now = datetime.now(UTC)
        hours_old = max(0.0, (now - access_timestamp).total_seconds() / 3600)

        # Clamp to reasonable range to avoid floating-point issues
        hours_old = min(hours_old, MAX_FRESHNESS_AGE_HOURS)  # Cap at 100 hours

        current_score = math.exp(-decay_lambda * hours_old)

        return FreshnessScore(
            hours_old=hours_old, decay_factor=decay_lambda, current_score=current_score
        )


class ContradictionWarning(BaseModel):
    """Warning indicating detected contradiction with other facts."""

    conflicting_node_ids: list[str] = Field(
        ..., min_length=1, description="Node IDs conflicting with this fact."
    )
    detected_by: str = Field(
        ..., min_length=1, description="Detection heuristic used (e.g., 'label_conflict')."
    )
    severity: ContradictionSeverity = Field(..., description="Severity level (low/medium/high).")
    description: str = Field(
        default="", description="Human-readable explanation of the contradiction."
    )


class ConfidenceBreakdown(BaseModel):
    """Aggregated confidence statistics over a set of evidence items."""

    average_confidence: float = Field(..., ge=0.0, le=1.0, description="Mean confidence score.")
    min_confidence: float = Field(..., ge=0.0, le=1.0, description="Minimum confidence in set.")
    max_confidence: float = Field(..., ge=0.0, le=1.0, description="Maximum confidence in set.")
    distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Histogram of confidence scores (buckets: 0-0.3, 0.3-0.6, 0.6-0.8, 0.8-1.0).",
    )
    is_low_confidence_set: bool = Field(
        default=False, description="True if average_confidence < threshold (0.3)."
    )
    total_items: int = Field(..., ge=0, description="Total evidence items in set.")

    @staticmethod
    def from_scores(scores: list[float]) -> ConfidenceBreakdown:
        """Construct ConfidenceBreakdown from list of confidence scores.

        Args:
            scores: List of confidence values (0.0-1.0).

        Returns:
            Computed ConfidenceBreakdown with statistics and distribution.
        """
        if not scores:
            return ConfidenceBreakdown(
                average_confidence=0.0,
                min_confidence=0.0,
                max_confidence=0.0,
                distribution={},
                is_low_confidence_set=True,
                total_items=0,
            )

        avg = sum(scores) / len(scores)
        distribution = {
            "0.0-0.3": sum(
                1 for s in scores if CONFIDENCE_LOWER_BOUND <= s < CONFIDENCE_BUCKET_LOW_UPPER_BOUND
            ),
            "0.3-0.6": sum(
                1
                for s in scores
                if CONFIDENCE_BUCKET_LOW_UPPER_BOUND <= s < CONFIDENCE_BUCKET_MEDIUM_UPPER_BOUND
            ),
            "0.6-0.8": sum(
                1
                for s in scores
                if CONFIDENCE_BUCKET_MEDIUM_UPPER_BOUND <= s < CONFIDENCE_BUCKET_HIGH_UPPER_BOUND
            ),
            "0.8-1.0": sum(
                1
                for s in scores
                if CONFIDENCE_BUCKET_HIGH_UPPER_BOUND <= s <= CONFIDENCE_UPPER_BOUND
            ),
        }

        return ConfidenceBreakdown(
            average_confidence=avg,
            min_confidence=min(scores),
            max_confidence=max(scores),
            distribution=distribution,
            is_low_confidence_set=avg < LOW_CONFIDENCE_THRESHOLD,
            total_items=len(scores),
        )


class SynthesisConfidenceSignal(BaseModel):
    """Confidence signals included in synthesis response for client awareness."""

    response_confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence of synthesis response."
    )
    evidence_confidence_breakdown: ConfidenceBreakdown = Field(
        ..., description="Aggregated confidence from evidence used."
    )
    freshness_range: tuple[float, float] = Field(
        ..., description="Min/max freshness scores in evidence (0.0-1.0)."
    )
    contradiction_warnings: list[ContradictionWarning] = Field(
        default_factory=list, description="Contradictions detected in evidence."
    )
    gating_applied: str = Field(
        default="none",
        description="Gating mode applied ('soft_signal', 'hard_reject', or 'none').",
    )
    gating_reason: str = Field(
        default="", description="Human-readable reason for gating decision if applied."
    )
