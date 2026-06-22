"""Evidence orchestration service for Phase 4 MindMap synthesis pipeline.

This module implements Phase 4D: orchestrates path retrieval (4B) +
neighbor retrieval (4C), builds EvidenceContext, tracks sufficiency,
and prepares evidence for synthesis stage.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.models.evidence import (
    EvidenceContext,
    EvidenceInsufficientReason,
    EvidenceItem,
    EvidenceSourceType,
)

if TYPE_CHECKING:
    from google.cloud import spanner

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
        # Heuristic: (paths >= 1 AND neighbors >= 1) OR (either >= 3)
        if path_count >= 1 and neighbor_count >= 1:
            return True
        if path_count >= 3 or neighbor_count >= 3:
            return True
        return False

    @staticmethod
    def insufficient_reasons(
        path_count: int,
        neighbor_count: int,
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
            if had_path_timeout and had_neighbor_timeout:
                reasons.append(EvidenceInsufficientReason.TIMEOUT)
            elif had_path_timeout:
                reasons.append(EvidenceInsufficientReason.TIMEOUT)
            elif had_neighbor_timeout:
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

    def __init__(self, client: spanner.Client) -> None:
        """Initialize evidence service.

        Args:
            client: Spanner client
        """
        self.client = client
        self._heuristic = EvidenceSufficiencyHeuristic()

    async def build_evidence_context(
        self,
        tenant_id: str,
        mined_entities: list[dict],
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
        # TODO: Phase 4D implementation
        # 1. Call PathFinder.find_paths() for each entity pair
        # 2. Call NeighborEnricher.enrich_neighbors() for retrieved entities
        # 3. Build EvidenceItem list with proper numbering
        # 4. Calculate totals (item count, char count)
        # 5. Determine sufficiency via heuristic
        # 6. If insufficient, populate insufficient_reasons
        # 7. Link to audit trail via MemoryAPI.record_audit_event()
        # 8. Return EvidenceContext
        logger.warning("build_evidence_context() not yet implemented (Phase 4D)")
        return EvidenceContext(
            is_empty=True,
            insufficient_reasons=[EvidenceInsufficientReason.UNKNOWN],
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
        # TODO: Phase 4D operational query
        # 1. Query ENGRAM_EVIDENCE WHERE TenantId = @tenant_id
        # 2. Filter by CreatedAt > NOW() - INTERVAL limit_hours
        # 3. Order by CreatedAt DESC
        # 4. Convert rows to EvidenceItem objects
        # 5. Return list
        logger.warning("get_evidence_context_for_tenant() not yet implemented")
        return []

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

        seen_ids = set()
        for item in context.items:
            if item.evidence_id in seen_ids:
                errors.append(f"Duplicate evidence_id: {item.evidence_id}")
            seen_ids.add(item.evidence_id)

        if context.total_chars <= 0 and context.total_items > 0:
            errors.append(
                f"Invalid char count: {context.total_chars} "
                f"but {context.total_items} items present"
            )

        return len(errors) == 0, errors
