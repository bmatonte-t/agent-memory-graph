"""Evidence orchestration service for Phase 4 MindMap synthesis pipeline.

This module implements Phase 4D: orchestrates path retrieval (4B) +
neighbor retrieval (4C), builds EvidenceContext, tracks sufficiency,
and prepares evidence for synthesis stage.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from src.db.spanner_client import SpannerClient
from src.integrations.google_sdk_wrappers import execute_sql_rows
from src.memory import retrieval
from src.models.confidence import FreshnessScore
from src.models.evidence import (
    EvidenceContext,
    EvidenceInsufficientReason,
    EvidenceItem,
    EvidenceSourceType,
    EvidenceSummary,
)
from src.security.validators import validate_tenant_id

MIN_BOTH_SIGNAL_COUNT = 1
MIN_ABUNDANT_SIGNAL_COUNT = 3
ENGRAM_EVIDENCE_ROW_COLUMNS = 9

logger = logging.getLogger(__name__)


class EvidenceSufficiencyHeuristic:
    """Conservative heuristic for evidence sufficiency (Phase 4D).

    Design: Only mark sufficient if grounding is clear:
    - Both paths AND neighbors available: sufficient
    - Either type >= 3 items: abundant single source, sufficient
    - Otherwise: insufficient (triggers Phase 4E synthesis caveat)

    NOTE: This is different from MindMap (which uses LLM judgment).
    We prefer explicit heuristic for auditability.
    """

    @staticmethod
    def is_sufficient(
        path_count: int,
        neighbor_count: int,
    ) -> bool:
        """Determine if evidence meets sufficiency threshold.

        Args:
            path_count: Number of path-based evidence items
            neighbor_count: Number of neighbor-based evidence items

        Returns:
            True if evidence sufficient, False otherwise
        """
        return bool(
            (path_count >= MIN_BOTH_SIGNAL_COUNT and neighbor_count >= MIN_BOTH_SIGNAL_COUNT)
            or path_count >= MIN_ABUNDANT_SIGNAL_COUNT
            or neighbor_count >= MIN_ABUNDANT_SIGNAL_COUNT
        )

    @staticmethod
    def insufficient_reasons(
        path_count: int,
        neighbor_count: int,
        *,
        had_path_timeout: bool = False,
        had_neighbor_timeout: bool = False,
        had_auth_denied: bool = False,
        graph_empty: bool = False,
    ) -> list[EvidenceInsufficientReason]:
        """Determine reasons why evidence was insufficient.

        Args:
            path_count: Number of path-based items
            neighbor_count: Number of neighbor-based items
            had_path_timeout: Path retrieval timed out
            had_neighbor_timeout: Neighbor retrieval timed out
            had_auth_denied: Authorization scope prevented access
            graph_empty: Tenant graph contains no nodes

        Returns:
            List of reasons (may be multiple)
        """
        reasons: list[EvidenceInsufficientReason] = []

        if graph_empty:
            reasons.append(EvidenceInsufficientReason.EMPTY_GRAPH)
            return reasons

        if path_count == 0 and neighbor_count == 0:
            # Determine which retrieval actually failed
            if had_path_timeout or had_neighbor_timeout:
                reasons.append(EvidenceInsufficientReason.TIMEOUT)
            elif had_auth_denied:
                reasons.append(EvidenceInsufficientReason.AUTHORIZATION_DENIED)
            else:
                # Empty results, not timeout
                if path_count == 0:
                    reasons.append(EvidenceInsufficientReason.NO_PATHS_FOUND)
                if neighbor_count == 0:
                    reasons.append(EvidenceInsufficientReason.NO_NEIGHBORS_FOUND)

        return reasons


class EvidenceService:
    """Orchestrates evidence retrieval and context building.

    Implements Phase 4D: calls PathFinder (4B) + NeighborEnricher (4C),
    builds EvidenceContext, tracks insufficiency, links to audit trail.
    """

    def __init__(self, client: object) -> None:
        """Initialize evidence service.

        Args:
            client: Spanner client
        """
        self.client = client
        self._heuristic = EvidenceSufficiencyHeuristic()

    async def build_evidence_context(
        self,
        tenant_id: str,
        mined_entities: list[str] | list[dict[str, Any]],
        session_id: str | None = None,
    ) -> EvidenceContext:
        """Build complete evidence context for synthesis stage.

        Orchestrates:
        1. Path retrieval between mined entities
        2. Neighbor enrichment for retrieved entities
        3. Sufficiency check
        4. Audit trail linkage

        Args:
            tenant_id: Tenant identifier
            mined_entities: List of entities mined from query
            session_id: Optional session ID for audit linkage

        Returns:
            EvidenceContext with all retrieved items + sufficiency signals

        Raises:
            ValueError: If inputs invalid
        """
        if not tenant_id or not tenant_id.strip():
            message = "tenant_id cannot be empty"
            raise ValueError(message)
        if not mined_entities:
            return EvidenceContext(
                is_empty=True,
                insufficient_reasons=[EvidenceInsufficientReason.EMPTY_GRAPH],
            )

        del session_id

        started = datetime.now(UTC)
        evidence_items: list[EvidenceItem] = []
        total_chars = 0
        path_count = 0
        neighbor_count = 0
        insufficient_reasons: list[EvidenceInsufficientReason] = []

        try:
            path_finder = retrieval.EvidentPathFinder(self.client)
            enricher = retrieval.NeighborEnricher(self.client)

            # Extract entity IDs from mined entities (dict format)
            entity_ids: list[str] = []
            for mined_entity in mined_entities:
                if isinstance(mined_entity, str):
                    entity_ids.append(mined_entity)
                else:
                    entity_value = mined_entity.get("entity_id", str(mined_entity))
                    entity_ids.append(str(entity_value))

            # Phase 4B: Retrieve paths between entities (pairwise)
            evidence_number = 1
            for i, start_entity in enumerate(entity_ids):
                for end_entity in entity_ids[i + 1 :]:
                    paths, _path_chars = await path_finder.find_paths(
                        tenant_id=tenant_id,
                        start_entity_id=start_entity,
                        end_entity_id=end_entity,
                    )
                    for path in paths:
                        evidence_items.append(
                            EvidenceItem(
                                evidence_id=f"evid_{evidence_number}",
                                source_type=EvidenceSourceType.PATH_BASED,
                                evidence_number=evidence_number,
                                graph_path=path,
                                serialized_form=path,
                                access_timestamp=started,
                                cognitive_weight=1.0,
                            )
                        )
                        total_chars += len(path)
                        path_count += 1
                        evidence_number += 1

            # Phase 4C: Enrich neighbors for each mined entity
            for entity_id in entity_ids:
                neighbors, _neighbor_chars = await enricher.enrich_neighbors(
                    tenant_id=tenant_id,
                    entity_id=entity_id,
                    context_flags={"skip_redundant_paths": True},
                )
                for neighbor in neighbors:
                    evidence_items.append(
                        EvidenceItem(
                            evidence_id=f"evid_{evidence_number}",
                            source_type=EvidenceSourceType.NEIGHBOR_BASED,
                            evidence_number=evidence_number,
                            graph_path=neighbor,
                            serialized_form=neighbor,
                            access_timestamp=started,
                            cognitive_weight=1.0,
                        )
                    )
                    total_chars += len(neighbor)
                    neighbor_count += 1
                    evidence_number += 1

        except Exception as error:
            logger.exception(
                "evidence_context.build_error",
                extra={"tenant_id": tenant_id, "error": str(error)},
            )
            insufficient_reasons.append(EvidenceInsufficientReason.UNKNOWN)

        # Phase 4D: Determine sufficiency
        is_sufficient = self._heuristic.is_sufficient(path_count, neighbor_count)
        if not is_sufficient and not insufficient_reasons:
            insufficient_reasons = self._heuristic.insufficient_reasons(path_count, neighbor_count)

        retrieval_latency_ms = (datetime.now(UTC) - started).total_seconds() * 1000

        return EvidenceContext(
            items=evidence_items,
            total_items=len(evidence_items),
            total_chars=total_chars,
            path_count=path_count,
            neighbor_count=neighbor_count,
            is_empty=len(evidence_items) == 0,
            is_sufficient=is_sufficient,
            insufficient_reasons=insufficient_reasons,
            retrieval_latency_ms=retrieval_latency_ms,
        )

    async def get_evidence_context_for_tenant(
        self,
        tenant_id: str,
        limit_hours: int = 24,
    ) -> list[EvidenceItem]:
        """Retrieve recent evidence for a tenant (operational query).

        Useful for: debugging evidence retrieval, analyzing reuse patterns,
        Phase 5 confidence gating (which evidence is most used).

        Args:
            tenant_id: Tenant identifier
            limit_hours: Look back this many hours (default: 24)

        Returns:
            List of recent EvidenceItem objects

        Raises:
            RuntimeError: If query fails
        """
        tenant_id = validate_tenant_id(tenant_id)

        try:
            database = SpannerClient.get_database()
            cutoff_time = datetime.now(UTC) - timedelta(hours=limit_hours)

            query_sql = """
                SELECT
                    EvidenceId, SourceType, EvidenceNumber,
                    GraphPath, SerializedForm, AccessTimestamp,
                    CognitiveWeight, AuditLogRef,
                    CreatedAt
                FROM ENGRAM_EVIDENCE
                WHERE TenantId = @tenant_id
                AND CreatedAt > @cutoff_time
                ORDER BY CreatedAt DESC
                LIMIT 1000
            """

            rows = execute_sql_rows(
                database,
                query_sql,
                {"tenant_id": tenant_id, "cutoff_time": cutoff_time},
            )

            evidence_items: list[EvidenceItem] = []
            for row in rows:
                if len(row) < ENGRAM_EVIDENCE_ROW_COLUMNS:
                    continue

                evidence_id = cast(str, row[0])
                source_type = cast(str, row[1])
                evidence_number = cast(int, row[2])
                graph_path = cast(str, row[3])
                serialized_form = cast(str, row[4])
                access_timestamp = cast(datetime, row[5])
                cognitive_weight = cast(float, row[6])
                audit_log_ref = cast(str, row[7])
                created_at = cast(datetime, row[8])

                item = EvidenceItem(
                    evidence_id=evidence_id,
                    source_type=EvidenceSourceType(source_type.lower()),
                    evidence_number=evidence_number,
                    graph_path=graph_path,
                    serialized_form=serialized_form,
                    access_timestamp=access_timestamp,
                    cognitive_weight=cognitive_weight,
                    audit_log_ref=audit_log_ref,
                    freshness_score=FreshnessScore.compute(created_at).current_score,
                )
                evidence_items.append(item)

            logger.info(
                "get_evidence_context_for_tenant retrieved %d items tenant_id=%s limit_hours=%d",
                len(evidence_items),
                tenant_id,
                limit_hours,
            )

        except Exception as e:
            logger.exception(
                "get_evidence_context_for_tenant failed tenant_id=%s limit_hours=%d",
                tenant_id,
                limit_hours,
            )
            message = f"get_evidence_context_for_tenant failed: {e}"
            raise RuntimeError(message) from e
        else:
            return evidence_items

    def validate_evidence_context(
        self,
        context: EvidenceContext,
    ) -> tuple[bool, list[str]]:
        """Validate EvidenceContext structure and consistency.

        Checks:
        - Total items count matches list length
        - Sufficiency heuristic consistent with counts
        - Character estimates reasonable
        - No duplicate evidence_ids

        Args:
            context: EvidenceContext to validate

        Returns:
            (is_valid, error_messages)
        """
        errors: list[str] = []

        if len(context.items) != context.total_items:
            errors.append(
                f"Item count mismatch: {len(context.items)} items "
                f"but total_items={context.total_items}"
            )

        expected_sufficiency = self._heuristic.is_sufficient(
            context.path_count,
            context.neighbor_count,
        )
        if expected_sufficiency != context.is_sufficient:
            errors.append(
                f"Sufficiency inconsistent: heuristic says {expected_sufficiency} "
                f"but is_sufficient={context.is_sufficient}"
            )

        seen_ids: set[str] = set()
        for item in context.items:
            if item.evidence_id in seen_ids:
                errors.append(f"Duplicate evidence_id: {item.evidence_id}")
            seen_ids.add(item.evidence_id)

        if context.total_chars <= 0 and context.total_items > 0:
            errors.append(
                f"Invalid char count: {context.total_chars} but {context.total_items} items present"
            )

        return len(errors) == 0, errors

    def _compute_freshness_scores(
        self,
        items: list[EvidenceItem],
        freshness_decay_lambda: float = 0.1,
    ) -> None:
        """Compute freshness decay scores for evidence items.

        Applies exponential decay formula: freshness = exp(-λ * hours_elapsed)
        where λ is the decay rate (default 0.1 per hour).

        Modifies items in-place, setting freshness_score field.

        Args:
            items: List of EvidenceItem objects
            freshness_decay_lambda: Decay rate parameter (0.01-1.0)
        """
        for item in items:
            # Use FreshnessScore.compute() for consistent decay logic
            freshness = FreshnessScore.compute(
                access_timestamp=item.access_timestamp,
                decay_lambda=freshness_decay_lambda,
            )
            # Cap to [0.0, 1.0] range
            item.freshness_score = max(0.0, min(1.0, freshness.current_score))

    def _aggregate_confidence_scores(
        self,
        items: list[EvidenceItem],
    ) -> tuple[float, float]:
        """Aggregate confidence scores across evidence items.

        Computes:
        - Minimum confidence (bottleneck signal for hard gating)
        - Average confidence (overall quality signal)

        Args:
            items: List of EvidenceItem objects

        Returns:
            (min_confidence, average_confidence) tuple, both 0.0-1.0
        """
        if not items:
            return 1.0, 1.0

        scores = [item.source_confidence_score for item in items]
        min_confidence = min(scores)
        average_confidence = sum(scores) / len(scores)

        return min_confidence, average_confidence

    def _aggregate_contradiction_warnings(
        self,
        items: list[EvidenceItem],
    ) -> list[dict[str, Any]]:
        """Aggregate contradiction flags across evidence items.

        Groups contradictions by:
        - severity level
        - conflicting node sets
        - count of contradictions per node

        Args:
            items: List of EvidenceItem objects

        Returns:
            List of aggregated contradiction warnings
        """
        if not items:
            return []

        # Track contradictions by severity
        contradictions_by_severity: dict[str, set[str]] = {
            "high": set(),
            "medium": set(),
            "low": set(),
        }

        for item in items:
            for flag_str in item.contradiction_flags:
                # Parse contradiction flags (format: "severity:node_id" or just flag)
                if ":" in flag_str:
                    severity, node_id = flag_str.split(":", 1)
                    if severity in contradictions_by_severity:
                        contradictions_by_severity[severity].add(node_id)
                else:
                    # Unstructured flag, treat as medium severity
                    contradictions_by_severity["medium"].add(flag_str)

        # Build aggregated warnings
        warnings: list[dict[str, Any]] = []
        for severity in ["high", "medium", "low"]:
            nodes = contradictions_by_severity[severity]
            if nodes:
                warnings.append(
                    {
                        "severity": severity,
                        "conflicting_count": len(nodes),
                        "nodes": sorted(nodes),
                    }
                )

        return warnings

    def enrich_evidence_context_with_phase5(
        self,
        context: EvidenceContext,
        freshness_decay_lambda: float = 0.1,
    ) -> None:
        """Enrich EvidenceContext items with Phase 5 confidence and freshness data.

        Modifies context in-place:
        - Computes freshness_score for each item using exponential decay
        - Items already have source_confidence_score from add_semantic_fact

        Args:
            context: EvidenceContext to enrich
            freshness_decay_lambda: Exponential decay rate (default 0.1)
        """
        if not context.items:
            return

        # Compute freshness scores
        self._compute_freshness_scores(
            context.items,
            freshness_decay_lambda=freshness_decay_lambda,
        )

    def build_evidence_summary(
        self,
        context: EvidenceContext,
    ) -> EvidenceSummary:
        """Build EvidenceSummary from EvidenceContext with Phase 5 signals.

        Aggregates:
        - Confidence scores (min, average)
        - Freshness scores (average)
        - Contradiction warnings

        Args:
            context: Complete EvidenceContext

        Returns:
            EvidenceSummary with Phase 5 metadata
        """
        # Compute confidence aggregates
        min_confidence, _ = self._aggregate_confidence_scores(context.items)

        # Compute average freshness
        average_freshness = None
        if context.items and any(item.freshness_score for item in context.items):
            freshness_scores = [
                item.freshness_score for item in context.items if item.freshness_score is not None
            ]
            if freshness_scores:
                average_freshness = sum(freshness_scores) / len(freshness_scores)

        # Aggregate contradiction warnings
        contradiction_warnings = self._aggregate_contradiction_warnings(context.items)

        return EvidenceSummary(
            total_items=context.total_items,
            path_count=context.path_count,
            neighbor_count=context.neighbor_count,
            is_sufficient=context.is_sufficient,
            is_empty=context.is_empty,
            insufficient_reasons=context.insufficient_reasons,
            retrieval_latency_ms=context.retrieval_latency_ms,
            min_confidence_in_set=min_confidence,
            average_freshness=average_freshness,
            contradiction_warnings=contradiction_warnings,
        )
