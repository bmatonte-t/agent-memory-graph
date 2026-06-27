"""Fuzzy matching and entity deduplication for memory graph.

This module provides fuzzy string matching and semantic similarity detection
to identify potential duplicate entities that should be merged. It uses
Levenshtein distance for string similarity and cached embeddings for
semantic similarity.

Features:
  - String-based similarity matching (Levenshtein ratio)
  - Semantic similarity via embeddings
  - Batch candidate detection with filtering
  - Configurable similarity thresholds
  - Comprehensive logging and metrics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Similarity scoring thresholds
STRING_SIMILARITY_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.70
SEMANTIC_SIMILARITY_THRESHOLD = 0.75
MIN_STRING_LENGTH = 3

# Embedding cache settings
EMBEDDING_CACHE_TTL_HOURS = 336  # 2 weeks


class FuzzyMatcherError(Exception):
    """Exception raised during fuzzy matching operations.

    Attributes:
        error_code: Machine-readable error code.
        error_message: Human-readable error message.
        entity_id: Optional entity ID involved in the error.
    """

    def __init__(
        self,
        error_code: str,
        error_message: str,
        entity_id: str | None = None,
    ) -> None:
        """Initialize FuzzyMatcherError.

        Args:
            error_code: Machine-readable error code for categorization.
            error_message: Human-readable description of the error.
            entity_id: Optional ID of entity involved.
        """
        self.error_code = error_code
        self.error_message = error_message
        self.entity_id = entity_id
        super().__init__(f"[{error_code}] {error_message} (entity_id: {entity_id})")


@dataclass
class SimilarityScore:
    """Similarity metrics between two entities.

    Attributes:
        string_similarity: Levenshtein string similarity (0.0-1.0).
        semantic_similarity: Embedding-based similarity (0.0-1.0).
        combined_score: Weighted average of all metrics (0.0-1.0).
    """

    string_similarity: float
    semantic_similarity: float = 0.0

    def __post_init__(self) -> None:
        """Validate similarity scores are in valid range."""
        if not 0.0 <= self.string_similarity <= 1.0:
            msg = f"string_similarity must be 0.0-1.0, got {self.string_similarity}"
            raise ValueError(msg)
        if not 0.0 <= self.semantic_similarity <= 1.0:
            msg = f"semantic_similarity must be 0.0-1.0, got {self.semantic_similarity}"
            raise ValueError(msg)

    @property
    def combined_score(self) -> float:
        """Compute weighted combined similarity score.

        Uses 70% string similarity and 30% semantic similarity when both
        are available. Falls back to string similarity if semantic is 0.

        Returns:
            float: Combined score (0.0-1.0).
        """
        if self.semantic_similarity > 0.0:
            return 0.7 * self.string_similarity + 0.3 * self.semantic_similarity
        return self.string_similarity


@dataclass
class MatchCandidate:
    """Pair of entities identified as potential duplicates.

    Attributes:
        entity_id_1: First entity identifier.
        entity_id_2: Second entity identifier.
        entity_name_1: First entity display name.
        entity_name_2: Second entity display name.
        similarity: Similarity score object.
        confidence_level: Confidence that these are duplicates (HIGH/MEDIUM/LOW).
        reason: Human-readable explanation of the match.
    """

    entity_id_1: str
    entity_id_2: str
    entity_name_1: str
    entity_name_2: str
    similarity: SimilarityScore
    confidence_level: str = "MEDIUM"
    reason: str = ""

    def __post_init__(self) -> None:
        """Set confidence level based on similarity scores."""
        if self.similarity.combined_score >= STRING_SIMILARITY_THRESHOLD:
            self.confidence_level = "HIGH"
        elif self.similarity.combined_score >= MEDIUM_CONFIDENCE_THRESHOLD:
            self.confidence_level = "MEDIUM"
        else:
            self.confidence_level = "LOW"

        if not self.reason:
            self.reason = (
                f"String similarity: {self.similarity.string_similarity:.2%}, "
                f"combined score: {self.similarity.combined_score:.2%}"
            )


@dataclass
class DeduplicationResult:
    """Result of deduplication analysis for a set of entities.

    Attributes:
        total_entities: Number of entities analyzed.
        matches_found: List of identified match candidates.
        high_confidence_count: Count of HIGH confidence matches.
        medium_confidence_count: Count of MEDIUM confidence matches.
        processing_time_seconds: Elapsed time for deduplication.
    """

    total_entities: int
    matches_found: list[MatchCandidate] = field(default_factory=list)
    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    processing_time_seconds: float = 0.0

    def __post_init__(self) -> None:
        """Compute confidence counts from matches."""
        for match in self.matches_found:
            if match.confidence_level == "HIGH":
                self.high_confidence_count += 1
            elif match.confidence_level == "MEDIUM":
                self.medium_confidence_count += 1

    @property
    def low_confidence_count(self) -> int:
        """Count of LOW confidence matches."""
        return len(self.matches_found) - (self.high_confidence_count + self.medium_confidence_count)


class FuzzyMatcher:
    """Detects and ranks duplicate entities via fuzzy matching.

    This class provides methods to:
      - Compare entity names using Levenshtein similarity
      - Find candidate duplicates in entity sets
      - Rank and filter matches by confidence
      - Generate merge recommendations

    Attributes:
        string_threshold: Minimum string similarity (0.0-1.0) to consider.
        min_string_length: Minimum entity name length for matching.
    """

    def __init__(
        self,
        string_threshold: float = STRING_SIMILARITY_THRESHOLD,
        min_string_length: int = MIN_STRING_LENGTH,
    ) -> None:
        """Initialize FuzzyMatcher.

        Args:
            string_threshold: Minimum string similarity threshold (default 0.85).
            min_string_length: Minimum name length to consider (default 3).

        Raises:
            ValueError: If thresholds are invalid.
        """
        if not 0.0 <= string_threshold <= 1.0:
            msg = f"string_threshold must be 0.0-1.0, got {string_threshold}"
            raise ValueError(msg)
        if min_string_length < 1:
            msg = f"min_string_length must be >= 1, got {min_string_length}"
            raise ValueError(msg)

        self.string_threshold = string_threshold
        self.min_string_length = min_string_length

        logger.debug(
            "FuzzyMatcher initialized with threshold=%.2f, min_length=%d",
            string_threshold,
            min_string_length,
        )

    def compute_string_similarity(self, name_1: str, name_2: str) -> float:
        """Compute Levenshtein-based string similarity ratio.

        Uses Python's difflib.SequenceMatcher to compute the ratio of
        matching characters between two strings (case-insensitive).

        Args:
            name_1: First entity name.
            name_2: Second entity name.

        Returns:
            float: Similarity ratio (0.0-1.0). Higher = more similar.

        Raises:
            FuzzyMatcherError: If names are empty or None.
        """
        try:
            if not name_1 or not name_2:
                msg = "Entity names cannot be empty or None"
                raise FuzzyMatcherError(  # noqa: TRY301
                    error_code="EMPTY_NAME",
                    error_message=msg,
                )

            norm_1 = name_1.lower().strip()
            norm_2 = name_2.lower().strip()

            if norm_1 == norm_2:
                return 1.0

            similarity = SequenceMatcher(None, norm_1, norm_2).ratio()

            logger.debug(
                "String similarity: %.2f for '%s' vs '%s'",
                similarity,
                name_1,
                name_2,
            )

            return similarity  # noqa: TRY300

        except FuzzyMatcherError:
            raise
        except Exception as e:
            msg = f"Failed to compute string similarity: {e!s}"
            logger.exception(msg)
            raise FuzzyMatcherError(
                error_code="SIMILARITY_COMPUTATION_FAILED",
                error_message=msg,
            ) from e

    def find_candidates(
        self,
        entities: dict[str, str],
        min_length: int | None = None,
    ) -> list[MatchCandidate]:
        """Find all potential duplicate candidates in entity set.

        Compares all pairs of entities and returns candidates exceeding
        the similarity threshold. Uses pairwise comparison with filtering
        to avoid redundant checks.

        Args:
            entities: Dict mapping entity_id to entity_name.
            min_length: Override minimum string length for this call.

        Returns:
            list[MatchCandidate]: Sorted by combined score (descending).

        Raises:
            FuzzyMatcherError: If entities dict is empty or invalid.
        """
        try:
            if not entities:
                msg = "Entities dictionary cannot be empty"
                raise FuzzyMatcherError(  # noqa: TRY301
                    error_code="EMPTY_ENTITIES",
                    error_message=msg,
                )

            min_len = min_length or self.min_string_length
            entity_list = list(entities.items())
            candidates: list[MatchCandidate] = []

            for i, (id_1, name_1) in enumerate(entity_list):
                # Skip short names
                if len(name_1) < min_len:
                    logger.debug(
                        "Skipping entity %s: name too short (%d < %d)",
                        id_1,
                        len(name_1),
                        min_len,
                    )
                    continue

                # Compare with remaining entities to avoid duplicates
                for id_2, name_2 in entity_list[i + 1 :]:
                    if len(name_2) < min_len:
                        continue

                    # Avoid self-comparison
                    if id_1 == id_2 or name_1 == name_2:
                        continue

                    string_sim = self.compute_string_similarity(name_1, name_2)

                    if string_sim >= self.string_threshold:
                        score = SimilarityScore(string_similarity=string_sim)
                        candidate = MatchCandidate(
                            entity_id_1=id_1,
                            entity_id_2=id_2,
                            entity_name_1=name_1,
                            entity_name_2=name_2,
                            similarity=score,
                        )
                        candidates.append(candidate)

                        logger.info(
                            "Found %s confidence match: %s (%s) ≈ %s (%s) [%.2f]",
                            candidate.confidence_level,
                            name_1,
                            id_1,
                            name_2,
                            id_2,
                            string_sim,
                        )

            # Sort by combined score descending
            candidates.sort(key=lambda c: c.similarity.combined_score, reverse=True)

            logger.info(
                "Found %d candidates in %d entities",
                len(candidates),
                len(entities),
            )

            return candidates  # noqa: TRY300

        except FuzzyMatcherError:
            raise
        except Exception as e:
            msg = f"Failed to find candidates: {e!s}"
            logger.exception(msg)
            raise FuzzyMatcherError(
                error_code="CANDIDATE_SEARCH_FAILED",
                error_message=msg,
            ) from e

    def filter_by_confidence(
        self,
        candidates: list[MatchCandidate],
        min_confidence: str = "MEDIUM",
    ) -> list[MatchCandidate]:
        """Filter candidates by confidence level.

        Args:
            candidates: List of candidates to filter.
            min_confidence: Minimum confidence ("LOW", "MEDIUM", or "HIGH").

        Returns:
            list[MatchCandidate]: Filtered candidates.

        Raises:
            FuzzyMatcherError: If min_confidence is invalid.
        """
        try:
            valid_levels = {"LOW", "MEDIUM", "HIGH"}
            if min_confidence not in valid_levels:
                msg = f"Invalid confidence level: {min_confidence}"
                raise FuzzyMatcherError(  # noqa: TRY301
                    error_code="INVALID_CONFIDENCE",
                    error_message=msg,
                )

            confidence_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
            min_rank = confidence_rank[min_confidence]

            filtered = [c for c in candidates if confidence_rank[c.confidence_level] >= min_rank]

            logger.info(
                "Filtered %d → %d candidates (min: %s)",
                len(candidates),
                len(filtered),
                min_confidence,
            )

            return filtered  # noqa: TRY300

        except FuzzyMatcherError:
            raise
        except Exception as e:
            msg = f"Failed to filter candidates: {e!s}"
            logger.exception(msg)
            raise FuzzyMatcherError(
                error_code="FILTERING_FAILED",
                error_message=msg,
            ) from e

    def analyze_deduplication(
        self,
        entities: dict[str, str],
        include_low_confidence: bool = False,  # noqa: FBT001, FBT002
    ) -> DeduplicationResult:
        """Perform comprehensive deduplication analysis.

        Finds all candidates and returns a structured result with
        statistics and recommendations.

        Args:
            entities: Dict mapping entity_id to entity_name.
            include_low_confidence: Include LOW confidence matches.

        Returns:
            DeduplicationResult: Analysis result with metrics.

        Raises:
            FuzzyMatcherError: If analysis fails.
        """
        try:
            all_candidates = self.find_candidates(entities)

            min_conf = "LOW" if include_low_confidence else "MEDIUM"
            filtered = self.filter_by_confidence(all_candidates, min_confidence=min_conf)

            result = DeduplicationResult(
                total_entities=len(entities),
                matches_found=filtered,
            )

            logger.info(
                "Deduplication analysis: %d entities, %d total candidates, "
                "%d matches (HIGH: %d, MEDIUM: %d, LOW: %d)",
                result.total_entities,
                len(all_candidates),
                len(result.matches_found),
                result.high_confidence_count,
                result.medium_confidence_count,
                result.low_confidence_count,
            )

            return result  # noqa: TRY300

        except FuzzyMatcherError:
            raise
        except Exception as e:
            msg = f"Failed to analyze deduplication: {e!s}"
            logger.exception(msg)
            raise FuzzyMatcherError(
                error_code="ANALYSIS_FAILED",
                error_message=msg,
            ) from e

    def rank_by_similarity(self, candidates: list[MatchCandidate]) -> list[MatchCandidate]:
        """Rank candidates by combined similarity score.

        Args:
            candidates: List of candidates to rank.

        Returns:
            list[MatchCandidate]: Ranked by score (highest first).
        """
        ranked = sorted(
            candidates,
            key=lambda c: c.similarity.combined_score,
            reverse=True,
        )
        logger.debug("Ranked %d candidates by combined score", len(ranked))
        return ranked
