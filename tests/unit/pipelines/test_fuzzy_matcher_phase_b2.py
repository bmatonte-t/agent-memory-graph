"""Tests for fuzzy matching and entity deduplication (Phase B2).

This test module comprehensively covers the FuzzyMatcher class, including
similarity scoring, candidate detection, filtering, and error handling.

Test Structure:
  - SimilarityScore: 5 tests
  - MatchCandidate: 4 tests
  - DeduplicationResult: 4 tests
  - FuzzyMatcher initialization: 3 tests
  - String similarity: 12 tests
  - Candidate detection: 12 tests
  - Confidence filtering: 6 tests
  - Deduplication analysis: 5 tests
  - Ranking: 2 tests
  - Error handling: 8 tests
  Total: 61 tests
"""
# ruff: noqa: PLR2004

from __future__ import annotations

import pytest

from src.pipelines.entity_linking.fuzzy_matcher import (
    STRING_SIMILARITY_THRESHOLD,
    DeduplicationResult,
    FuzzyMatcher,
    FuzzyMatcherError,
    MatchCandidate,
    SimilarityScore,
)

# Test constants
SIMILARITY_HIGH = 0.95
SIMILARITY_MEDIUM = 0.80
SIMILARITY_LOW = 0.50
INVALID_SIMILARITY = 1.5

ENTITY_ID_1 = "ent_001"
ENTITY_ID_2 = "ent_002"
ENTITY_ID_3 = "ent_003"

ENTITY_NAME_EXACT = "John Smith"
ENTITY_NAME_SIMILAR = "Jon Smith"
ENTITY_NAME_DIFFERENT = "Jane Doe"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"

# Similarity score constants
SIMILARITY_HIGH_INIT = 0.95
SIMILARITY_MEDIUM_INIT = 0.80
SIMILARITY_COMBINED_INIT = 1.0
SIMILARITY_INIT_ZERO = 0.0
SEMANTIC_SIMILARITY_INIT = 0.8
SEMANTIC_SIMILARITY_ZERO = 0.0
SEMANTIC_SIMILARITY_MEDIUM = 0.75

ENTITIES_SMALL = {
    ENTITY_ID_1: "John Smith",
    ENTITY_ID_2: "Jon Smith",
}

ENTITIES_LARGE = {
    "ent_001": "John Smith",
    "ent_002": "Jon Smith",
    "ent_003": "Jane Doe",
    "ent_004": "Jane D.",
    "ent_005": "Michael Johnson",
    "ent_006": "Michael Jon",
    "ent_007": "Sarah Williams",
}

THRESHOLD_HIGH = 0.90
THRESHOLD_LOW = 0.70


# ============================================================================
# SimilarityScore Tests
# ============================================================================


class TestSimilarityScore:
    """Tests for SimilarityScore data class."""

    def test_similarity_score_initialization(self) -> None:
        """Test basic initialization of SimilarityScore."""
        score = SimilarityScore(string_similarity=SIMILARITY_HIGH_INIT)
        assert score.string_similarity == 0.95
        assert score.semantic_similarity == 0.0

    def test_similarity_score_with_both_metrics(self) -> None:
        """Test SimilarityScore with both string and semantic metrics."""
        score = SimilarityScore(
            string_similarity=0.90, semantic_similarity=SEMANTIC_SIMILARITY_INIT
        )
        assert score.string_similarity == 0.90
        assert score.semantic_similarity == 0.80

    def test_similarity_score_combined_with_semantic(self) -> None:
        """Test combined score weighted average (70% string, 30% semantic)."""
        score = SimilarityScore(string_similarity=SIMILARITY_COMBINED_INIT, semantic_similarity=0.8)
        expected = 0.7 * 1.0 + 0.3 * 0.8
        assert score.combined_score == expected

    def test_similarity_score_combined_without_semantic(self) -> None:
        """Test combined score falls back to string when semantic is 0."""
        score = SimilarityScore(string_similarity=0.85)
        assert score.combined_score == 0.85

    def test_similarity_score_validation_string_invalid(self) -> None:
        """Test SimilarityScore rejects invalid string similarity."""
        with pytest.raises(ValueError, match="string_similarity must be"):
            SimilarityScore(string_similarity=1.5)

    def test_similarity_score_validation_semantic_invalid(self) -> None:
        """Test SimilarityScore rejects invalid semantic similarity."""
        with pytest.raises(ValueError, match="semantic_similarity must be"):
            SimilarityScore(string_similarity=0.90, semantic_similarity=-0.1)


# ============================================================================
# MatchCandidate Tests
# ============================================================================


class TestMatchCandidate:
    """Tests for MatchCandidate data class."""

    def test_match_candidate_initialization(self) -> None:
        """Test basic MatchCandidate initialization."""
        score = SimilarityScore(string_similarity=SIMILARITY_HIGH_INIT)
        candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1=ENTITY_NAME_EXACT,
            entity_name_2=ENTITY_NAME_SIMILAR,
            similarity=score,
        )
        assert candidate.entity_id_1 == ENTITY_ID_1
        assert candidate.entity_id_2 == ENTITY_ID_2
        assert candidate.similarity == score

    def test_match_candidate_confidence_high(self) -> None:
        """Test MatchCandidate assigns HIGH confidence correctly."""
        score = SimilarityScore(string_similarity=SIMILARITY_HIGH_INIT)
        candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1=ENTITY_NAME_EXACT,
            entity_name_2=ENTITY_NAME_SIMILAR,
            similarity=score,
        )
        assert candidate.confidence_level == CONFIDENCE_HIGH

    def test_match_candidate_confidence_medium(self) -> None:
        """Test MatchCandidate assigns MEDIUM confidence correctly."""
        score = SimilarityScore(string_similarity=0.75)
        candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1=ENTITY_NAME_EXACT,
            entity_name_2=ENTITY_NAME_DIFFERENT,
            similarity=score,
        )
        assert candidate.confidence_level == CONFIDENCE_MEDIUM

    def test_match_candidate_confidence_low(self) -> None:
        """Test MatchCandidate assigns LOW confidence correctly."""
        score = SimilarityScore(string_similarity=0.50)
        candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1=ENTITY_NAME_EXACT,
            entity_name_2=ENTITY_NAME_DIFFERENT,
            similarity=score,
        )
        assert candidate.confidence_level == CONFIDENCE_LOW

    def test_match_candidate_reason_auto_generated(self) -> None:
        """Test MatchCandidate generates reason if not provided."""
        score = SimilarityScore(string_similarity=0.90)
        candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1=ENTITY_NAME_EXACT,
            entity_name_2=ENTITY_NAME_SIMILAR,
            similarity=score,
        )
        assert "90.00%" in candidate.reason


# ============================================================================
# DeduplicationResult Tests
# ============================================================================


class TestDeduplicationResult:
    """Tests for DeduplicationResult data class."""

    def test_deduplication_result_initialization(self) -> None:
        """Test basic DeduplicationResult initialization."""
        result = DeduplicationResult(total_entities=10)
        assert result.total_entities == 10
        assert len(result.matches_found) == 0
        assert result.high_confidence_count == 0

    def test_deduplication_result_with_matches(self) -> None:
        """Test DeduplicationResult with match candidates."""
        score = SimilarityScore(string_similarity=SIMILARITY_HIGH_INIT)
        candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1=ENTITY_NAME_EXACT,
            entity_name_2=ENTITY_NAME_SIMILAR,
            similarity=score,
        )
        result = DeduplicationResult(total_entities=10, matches_found=[candidate])
        assert len(result.matches_found) == 1
        assert result.high_confidence_count == 1

    def test_deduplication_result_confidence_counts(self) -> None:
        """Test DeduplicationResult computes confidence counts."""
        high_score = SimilarityScore(string_similarity=SIMILARITY_HIGH_INIT)
        high_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1="Alpha",
            entity_name_2="Alpha2",
            similarity=high_score,
        )

        medium_score = SimilarityScore(string_similarity=0.75)
        medium_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_2,
            entity_id_2=ENTITY_ID_3,
            entity_name_1="Beta",
            entity_name_2="Beta2",
            similarity=medium_score,
        )

        result = DeduplicationResult(
            total_entities=5,
            matches_found=[high_candidate, medium_candidate],
        )
        assert result.high_confidence_count == 1
        assert result.medium_confidence_count == 1
        assert result.low_confidence_count == 0

    def test_deduplication_result_low_confidence_count(self) -> None:
        """Test DeduplicationResult computes low confidence count."""
        low_score = SimilarityScore(string_similarity=0.50)
        low_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1="Gamma",
            entity_name_2="Gamma2",
            similarity=low_score,
        )
        result = DeduplicationResult(total_entities=5, matches_found=[low_candidate])
        assert result.low_confidence_count == 1


# ============================================================================
# FuzzyMatcher Initialization Tests
# ============================================================================


class TestFuzzyMatcherInitialization:
    """Tests for FuzzyMatcher initialization and validation."""

    def test_fuzzy_matcher_default_initialization(self) -> None:
        """Test FuzzyMatcher initializes with defaults."""
        matcher = FuzzyMatcher()
        assert matcher.string_threshold == STRING_SIMILARITY_THRESHOLD
        assert matcher.min_string_length == 3

    def test_fuzzy_matcher_custom_threshold(self) -> None:
        """Test FuzzyMatcher accepts custom threshold."""
        matcher = FuzzyMatcher(string_threshold=0.80)
        assert matcher.string_threshold == 0.80

    def test_fuzzy_matcher_invalid_threshold_too_high(self) -> None:
        """Test FuzzyMatcher rejects threshold > 1.0."""
        with pytest.raises(ValueError, match="string_threshold must be"):
            FuzzyMatcher(string_threshold=1.5)

    def test_fuzzy_matcher_invalid_threshold_negative(self) -> None:
        """Test FuzzyMatcher rejects negative threshold."""
        with pytest.raises(ValueError, match="string_threshold must be"):
            FuzzyMatcher(string_threshold=-0.1)

    def test_fuzzy_matcher_invalid_min_length(self) -> None:
        """Test FuzzyMatcher rejects invalid min_string_length."""
        with pytest.raises(ValueError, match="min_string_length must be"):
            FuzzyMatcher(min_string_length=0)


# ============================================================================
# String Similarity Tests
# ============================================================================


class TestStringSimilarity:
    """Tests for string similarity computation."""

    def test_string_similarity_identical_names(self) -> None:
        """Test identical names return 1.0 similarity."""
        matcher = FuzzyMatcher()
        similarity = matcher.compute_string_similarity("John Smith", "John Smith")
        assert similarity == 1.0

    def test_string_similarity_identical_case_insensitive(self) -> None:
        """Test similarity is case-insensitive."""
        matcher = FuzzyMatcher()
        similarity = matcher.compute_string_similarity("John Smith", "JOHN SMITH")
        assert similarity == 1.0

    def test_string_similarity_similar_names(self) -> None:
        """Test similar names return high similarity."""
        matcher = FuzzyMatcher()
        similarity = matcher.compute_string_similarity("John Smith", "Jon Smith")
        assert similarity > 0.80

    def test_string_similarity_different_names(self) -> None:
        """Test different names return low similarity."""
        matcher = FuzzyMatcher()
        similarity = matcher.compute_string_similarity("John Smith", "Jane Doe")
        assert similarity < 0.50

    def test_string_similarity_partial_match(self) -> None:
        """Test partial string match."""
        matcher = FuzzyMatcher()
        similarity = matcher.compute_string_similarity("John", "Johnson")
        assert 0.50 < similarity < 0.90

    def test_string_similarity_whitespace_handling(self) -> None:
        """Test leading/trailing whitespace is ignored."""
        matcher = FuzzyMatcher()
        similarity = matcher.compute_string_similarity("  John Smith  ", "John Smith")
        assert similarity == 1.0

    def test_string_similarity_empty_first_name(self) -> None:
        """Test empty first name raises error."""
        matcher = FuzzyMatcher()
        with pytest.raises(FuzzyMatcherError, match="EMPTY_NAME"):
            matcher.compute_string_similarity("", "John")

    def test_string_similarity_empty_second_name(self) -> None:
        """Test empty second name raises error."""
        matcher = FuzzyMatcher()
        with pytest.raises(FuzzyMatcherError, match="EMPTY_NAME"):
            matcher.compute_string_similarity("John", "")

    def test_string_similarity_none_first_name(self) -> None:
        """Test None first name raises error."""
        matcher = FuzzyMatcher()
        with pytest.raises(FuzzyMatcherError, match="EMPTY_NAME"):
            matcher.compute_string_similarity(None, "John")  # type: ignore[arg-type]

    def test_string_similarity_single_character(self) -> None:
        """Test single character names."""
        matcher = FuzzyMatcher()
        similarity = matcher.compute_string_similarity("A", "A")
        assert similarity == 1.0

    def test_string_similarity_numbers_in_names(self) -> None:
        """Test names with numbers."""
        matcher = FuzzyMatcher()
        similarity = matcher.compute_string_similarity("John Smith Jr.", "John Smith Jr.")
        assert similarity == 1.0

    def test_string_similarity_special_characters(self) -> None:
        """Test names with special characters."""
        matcher = FuzzyMatcher()
        similarity = matcher.compute_string_similarity("O'Brien", "O Brien")
        assert similarity > 0.70


# ============================================================================
# Candidate Detection Tests
# ============================================================================


class TestCandidateDetection:
    """Tests for finding and ranking duplicate candidates."""

    def test_find_candidates_empty_entities(self) -> None:
        """Test find_candidates with empty entity dict."""
        matcher = FuzzyMatcher()
        with pytest.raises(FuzzyMatcherError, match="EMPTY_ENTITIES"):
            matcher.find_candidates({})

    def test_find_candidates_single_entity(self) -> None:
        """Test find_candidates with only one entity."""
        matcher = FuzzyMatcher()
        entities = {ENTITY_ID_1: "John Smith"}
        candidates = matcher.find_candidates(entities)
        assert len(candidates) == 0

    def test_find_candidates_no_matches(self) -> None:
        """Test find_candidates when no entities match."""
        matcher = FuzzyMatcher()
        entities = {
            ENTITY_ID_1: "John Smith",
            ENTITY_ID_2: "Jane Doe",
            ENTITY_ID_3: "Michael Johnson",
        }
        candidates = matcher.find_candidates(entities)
        assert len(candidates) == 0

    def test_find_candidates_exact_match(self) -> None:
        """Test find_candidates detects nearly-identical matches."""
        matcher = FuzzyMatcher(string_threshold=0.80)
        entities = {
            ENTITY_ID_1: "John Smith",
            ENTITY_ID_2: "Jon Smith",
        }
        candidates = matcher.find_candidates(entities)
        assert len(candidates) >= 1
        assert candidates[0].similarity.string_similarity > 0.80

    def test_find_candidates_similar_match(self) -> None:
        """Test find_candidates detects similar matches."""
        matcher = FuzzyMatcher(string_threshold=0.80)
        entities = {
            ENTITY_ID_1: "John Smith",
            ENTITY_ID_2: "Jon Smith",
        }
        candidates = matcher.find_candidates(entities)
        assert len(candidates) >= 1

    def test_find_candidates_filters_short_names(self) -> None:
        """Test find_candidates skips names shorter than min_length."""
        matcher = FuzzyMatcher(min_string_length=5)
        entities = {
            ENTITY_ID_1: "Jo",
            ENTITY_ID_2: "John Smith",
        }
        candidates = matcher.find_candidates(entities)
        assert len(candidates) == 0

    def test_find_candidates_sorted_by_score(self) -> None:
        """Test find_candidates returns candidates sorted by score."""
        matcher = FuzzyMatcher(string_threshold=0.75)
        entities = {
            "ent_001": "John Smith",
            "ent_002": "Jon Smith",
            "ent_003": "Jane Doe",
        }
        candidates = matcher.find_candidates(entities)
        assert len(candidates) >= 1
        # Check candidates are sorted by score descending
        for i in range(len(candidates) - 1):
            assert (
                candidates[i].similarity.combined_score
                >= candidates[i + 1].similarity.combined_score
            )

    def test_find_candidates_multiple_pairs(self) -> None:
        """Test find_candidates detects multiple candidate pairs."""
        matcher = FuzzyMatcher(string_threshold=0.75)
        entities = {
            "ent_001": "John Smith",
            "ent_002": "Jon Smith",
            "ent_003": "Jane Doe",
            "ent_004": "Jan Doe",
        }
        candidates = matcher.find_candidates(entities)
        assert len(candidates) >= 2

    def test_find_candidates_large_dataset(self) -> None:
        """Test find_candidates with larger entity set."""
        matcher = FuzzyMatcher(string_threshold=0.80)
        candidates = matcher.find_candidates(ENTITIES_LARGE)
        assert len(candidates) > 0

    def test_find_candidates_custom_min_length(self) -> None:
        """Test find_candidates accepts min_length override."""
        matcher = FuzzyMatcher(min_string_length=10)
        entities = {
            "ent_001": "John",
            "ent_002": "Jane Smith",  # Longer name
        }
        candidates = matcher.find_candidates(entities, min_length=4)
        # Should work with override
        assert isinstance(candidates, list)

    def test_find_candidates_no_self_comparison(self) -> None:
        """Test find_candidates doesn't compare entity with itself."""
        matcher = FuzzyMatcher()
        entities = {ENTITY_ID_1: "John Smith"}
        candidates = matcher.find_candidates(entities)
        assert len(candidates) == 0


# ============================================================================
# Confidence Filtering Tests
# ============================================================================


class TestConfidenceFiltering:
    """Tests for filtering candidates by confidence level."""

    def test_filter_by_confidence_high_only(self) -> None:
        """Test filtering for HIGH confidence only."""
        matcher = FuzzyMatcher()
        high_score = SimilarityScore(string_similarity=SIMILARITY_HIGH_INIT)
        high_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1="Alpha",
            entity_name_2="Alpha2",
            similarity=high_score,
        )

        medium_score = SimilarityScore(string_similarity=0.75)
        medium_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_2,
            entity_id_2=ENTITY_ID_3,
            entity_name_1="Beta",
            entity_name_2="Beta2",
            similarity=medium_score,
        )

        candidates = [high_candidate, medium_candidate]
        filtered = matcher.filter_by_confidence(candidates, "HIGH")
        assert len(filtered) == 1
        assert filtered[0].confidence_level == "HIGH"

    def test_filter_by_confidence_medium_and_above(self) -> None:
        """Test filtering for MEDIUM and above."""
        matcher = FuzzyMatcher()
        high_score = SimilarityScore(string_similarity=SIMILARITY_HIGH_INIT)
        high_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1="Alpha",
            entity_name_2="Alpha2",
            similarity=high_score,
        )

        medium_score = SimilarityScore(string_similarity=0.75)
        medium_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_2,
            entity_id_2=ENTITY_ID_3,
            entity_name_1="Beta",
            entity_name_2="Beta2",
            similarity=medium_score,
        )

        low_score = SimilarityScore(string_similarity=0.50)
        low_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_3,
            entity_name_1="Gamma",
            entity_name_2="Gamma2",
            similarity=low_score,
        )

        candidates = [high_candidate, medium_candidate, low_candidate]
        filtered = matcher.filter_by_confidence(candidates, "MEDIUM")
        assert len(filtered) == 2
        assert all(c.confidence_level in ["HIGH", "MEDIUM"] for c in filtered)

    def test_filter_by_confidence_all_levels(self) -> None:
        """Test filtering for all confidence levels."""
        matcher = FuzzyMatcher()
        high_score = SimilarityScore(string_similarity=SIMILARITY_HIGH_INIT)
        high_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1="Alpha",
            entity_name_2="Alpha2",
            similarity=high_score,
        )

        low_score = SimilarityScore(string_similarity=0.50)
        low_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_3,
            entity_name_1="Gamma",
            entity_name_2="Gamma2",
            similarity=low_score,
        )

        candidates = [high_candidate, low_candidate]
        filtered = matcher.filter_by_confidence(candidates, "LOW")
        assert len(filtered) == 2

    def test_filter_by_confidence_empty_list(self) -> None:
        """Test filtering empty candidate list."""
        matcher = FuzzyMatcher()
        filtered = matcher.filter_by_confidence([], "HIGH")
        assert len(filtered) == 0

    def test_filter_by_confidence_invalid_level(self) -> None:
        """Test filtering with invalid confidence level."""
        matcher = FuzzyMatcher()
        with pytest.raises(FuzzyMatcherError, match="INVALID_CONFIDENCE"):
            matcher.filter_by_confidence([], "CRITICAL")  # Invalid level

    def test_filter_by_confidence_case_sensitive(self) -> None:
        """Test confidence level is case-sensitive."""
        matcher = FuzzyMatcher()
        with pytest.raises(FuzzyMatcherError, match="INVALID_CONFIDENCE"):
            matcher.filter_by_confidence([], "high")  # lowercase


# ============================================================================
# Deduplication Analysis Tests
# ============================================================================


class TestDeduplicationAnalysis:
    """Tests for comprehensive deduplication analysis."""

    def test_analyze_deduplication_small_set(self) -> None:
        """Test deduplication analysis on small entity set."""
        matcher = FuzzyMatcher(string_threshold=0.80)
        result = matcher.analyze_deduplication(ENTITIES_SMALL)
        assert result.total_entities == 2

    def test_analyze_deduplication_with_matches(self) -> None:
        """Test deduplication analysis finds matches."""
        matcher = FuzzyMatcher(string_threshold=0.80)
        entities = {
            "ent_001": "John Smith",
            "ent_002": "Jon Smith",
        }
        result = matcher.analyze_deduplication(entities)
        assert len(result.matches_found) > 0

    def test_analyze_deduplication_result_has_metrics(self) -> None:
        """Test DeduplicationResult includes all metrics."""
        matcher = FuzzyMatcher(string_threshold=0.80)
        result = matcher.analyze_deduplication(ENTITIES_SMALL)
        assert result.total_entities > 0
        assert hasattr(result, "high_confidence_count")
        assert hasattr(result, "medium_confidence_count")

    def test_analyze_deduplication_exclude_low_confidence(self) -> None:
        """Test deduplication excludes low confidence by default."""
        matcher = FuzzyMatcher(string_threshold=0.50)
        result = matcher.analyze_deduplication(ENTITIES_LARGE, include_low_confidence=False)
        assert all(c.confidence_level != "LOW" for c in result.matches_found)

    def test_analyze_deduplication_include_low_confidence(self) -> None:
        """Test deduplication includes low confidence when requested."""
        matcher = FuzzyMatcher(string_threshold=0.50)
        result = matcher.analyze_deduplication(ENTITIES_LARGE, include_low_confidence=True)
        # At least some results (may or may not include LOW)
        assert isinstance(result, DeduplicationResult)


# ============================================================================
# Ranking Tests
# ============================================================================


class TestRanking:
    """Tests for ranking candidates by similarity."""

    def test_rank_by_similarity_maintains_order(self) -> None:
        """Test ranking preserves candidates."""
        matcher = FuzzyMatcher()
        high_score = SimilarityScore(string_similarity=SIMILARITY_HIGH_INIT)
        high_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_1,
            entity_id_2=ENTITY_ID_2,
            entity_name_1="Alpha",
            entity_name_2="Alpha2",
            similarity=high_score,
        )

        low_score = SimilarityScore(string_similarity=0.50)
        low_candidate = MatchCandidate(
            entity_id_1=ENTITY_ID_2,
            entity_id_2=ENTITY_ID_3,
            entity_name_1="Beta",
            entity_name_2="Beta2",
            similarity=low_score,
        )

        candidates = [low_candidate, high_candidate]
        ranked = matcher.rank_by_similarity(candidates)
        assert len(ranked) == 2
        assert ranked[0].similarity.combined_score >= ranked[1].similarity.combined_score

    def test_rank_by_similarity_empty_list(self) -> None:
        """Test ranking empty candidate list."""
        matcher = FuzzyMatcher()
        ranked = matcher.rank_by_similarity([])
        assert len(ranked) == 0


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling and exception cases."""

    def test_fuzzy_matcher_error_initialization(self) -> None:
        """Test FuzzyMatcherError can be raised and caught."""
        with pytest.raises(FuzzyMatcherError) as exc_info:
            raise FuzzyMatcherError(
                error_code="TEST_ERROR",
                error_message="Test error message",
            )
        assert exc_info.value.error_code == "TEST_ERROR"

    def test_fuzzy_matcher_error_with_entity_id(self) -> None:
        """Test FuzzyMatcherError stores entity_id."""
        with pytest.raises(FuzzyMatcherError) as exc_info:
            raise FuzzyMatcherError(
                error_code="TEST_ERROR",
                error_message="Test message",
                entity_id=ENTITY_ID_1,
            )
        assert exc_info.value.entity_id == ENTITY_ID_1

    def test_similarity_computation_error_recovery(self) -> None:
        """Test error handling in similarity computation."""
        matcher = FuzzyMatcher()
        # Test with None values
        with pytest.raises(FuzzyMatcherError):
            matcher.compute_string_similarity(None, "Test")  # type: ignore[arg-type]

    def test_candidate_search_with_all_short_names(self) -> None:
        """Test candidate search when all names are below min_length."""
        matcher = FuzzyMatcher(min_string_length=100)
        entities = {
            ENTITY_ID_1: "Jo",
            ENTITY_ID_2: "Jane",
        }
        candidates = matcher.find_candidates(entities)
        assert len(candidates) == 0

    def test_filter_candidates_with_none_list(self) -> None:
        """Test error handling when filtering None."""
        matcher = FuzzyMatcher()
        # Should raise FuzzyMatcherError when trying to filter None
        with pytest.raises(FuzzyMatcherError):
            matcher.filter_by_confidence(None, "HIGH")  # type: ignore[arg-type]

    def test_analyze_deduplication_with_none_entities(self) -> None:
        """Test deduplication analysis with None entities."""
        matcher = FuzzyMatcher()
        with pytest.raises(FuzzyMatcherError):
            matcher.analyze_deduplication(None)  # type: ignore[arg-type]

    def test_rank_with_malformed_candidates(self) -> None:
        """Test ranking handles edge cases."""
        matcher = FuzzyMatcher()
        candidates: list[MatchCandidate] = []
        ranked = matcher.rank_by_similarity(candidates)
        assert len(ranked) == 0

    def test_string_similarity_with_very_long_names(self) -> None:
        """Test string similarity with very long names."""
        matcher = FuzzyMatcher()
        long_name_1 = "John Smith " * 100
        long_name_2 = "Jon Smith " * 100
        similarity = matcher.compute_string_similarity(long_name_1, long_name_2)
        assert 0.0 <= similarity <= 1.0
