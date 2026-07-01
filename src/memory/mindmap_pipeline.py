"""MindMap query pipeline implementation scaffold for Phase 2."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field, model_validator

from src.db.spanner_client import SpannerClient
from src.integrations.google_sdk_wrappers import generate_generative_ai_text
from src.memory.api import MemoryAPI
from src.memory.evidence_service import EvidenceService
from src.models.confidence import (
    ConfidenceBreakdown,
    ContradictionSeverity,
    ContradictionWarning,
    SynthesisConfidenceSignal,
)
from src.models.evidence import EvidenceContext, EvidenceSummary
from src.models.mindmap import (
    AggregationResult,
    EvidenceEdge,
    EvidenceNode,
    EvidencePath,
    MindMapResponse,
    MindMapTrace,
    MinedEntity,
    MiningResult,
    PipelineErrorCode,
    PipelineStage,
    SerializationResult,
    SerializedFact,
    StageTiming,
    SynthesisResult,
)
from src.observability.metrics import pipeline_execution_histogram, pipeline_fact_counter
from src.observability.tracing import trace_span

logger = logging.getLogger(__name__)


def _is_graph_query_unsupported(error: Exception) -> bool:
    """Return whether an error indicates unsupported graph query syntax.

    Args:
        error: Runtime error raised by Spanner query execution.

    Returns:
        bool: True when graph query syntax is unsupported by the backend.
    """
    message = str(error).lower()
    return (
        "unexpected keyword match" in message
        or 'expected "]" but got "*"' in message
        or ("syntax error" in message and "graph" in message)
    )


if TYPE_CHECKING:
    from src.security.governance import AuthorizationScope


class MindMapPipelineError(RuntimeError):
    """Error raised when a MindMap stage cannot complete correctly."""

    def __init__(
        self,
        *,
        stage: PipelineStage,
        code: PipelineErrorCode,
        message: str,
    ) -> None:
        """Initialize stage error details.

        Args:
            stage (PipelineStage): Failing pipeline stage.
            code (PipelineErrorCode): Stable error code for clients and metrics.
            message (str): Human readable error message.
        """
        super().__init__(message)
        self.stage = stage
        self.code = code


class GatingConfig(BaseModel):
    """Configurable penalty coefficients for synthesis confidence gating.

    Replaces magic numbers in the contradiction penalty calculation so that
    callers can tune penalty sensitivity without touching pipeline internals.
    """

    per_contradiction_penalty: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Confidence penalty applied per contradiction warning.",
    )
    high_severity_bonus_penalty: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Additional penalty when any contradiction has HIGH severity.",
    )
    max_total_penalty: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Upper bound on total confidence penalty from contradictions.",
    )


class MindMapConfig(BaseModel):
    """Runtime configuration for MindMap execution."""

    cognitive_weight_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    max_hops: int = Field(default=3, ge=1, le=6)
    max_paths: int = Field(default=20, ge=1)
    max_evidence_nodes: int = Field(default=200, ge=1)
    extraction_model_name: str = Field(default="gemini-2.5-flash")
    synthesis_model_name: str = Field(default="gemini-2.5-pro")
    use_vertex_mining: bool = Field(default=False)
    use_vertex_synthesis: bool = Field(default=False)
    use_spanner_aggregation: bool = Field(default=False)
    use_deterministic_aggregation: bool = Field(
        default=False,
        description=(
            "When True, use deterministic (non-graph) aggregation; "
            "False uses graph-backed aggregation by default (Phase 4 best practice)."
        ),
    )
    enable_trace_recording: bool = Field(default=True)
    # Phase 5: Confidence and freshness configuration
    confidence_threshold: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Min confidence for synthesis gating (Phase 5)."
    )
    freshness_threshold: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Min freshness score for evidence inclusion (Phase 5).",
    )
    freshness_decay_lambda: float = Field(
        default=0.1,
        ge=0.01,
        le=1.0,
        description="Exponential decay rate for freshness (Phase 5).",
    )
    enable_contradiction_detection: bool = Field(
        default=True, description="Enable contradiction detection heuristics (Phase 5)."
    )
    synthesis_gating_mode: str = Field(
        default="soft_signal",
        description=(
            "Gating strategy: 'soft_signal' (annotate LLM prompt) or "
            "'hard_reject' (filter low-confidence evidence) (Phase 5)."
        ),
    )
    gating: GatingConfig = Field(
        default_factory=GatingConfig,
        description="Configurable penalty coefficients for contradiction-based gating.",
    )

    @model_validator(mode="after")
    def aggregation_flags_mutually_exclusive(self) -> "MindMapConfig":
        """Enforce that use_spanner_aggregation and use_deterministic_aggregation cannot both be True."""
        if self.use_spanner_aggregation and self.use_deterministic_aggregation:
            raise ValueError(
                "use_spanner_aggregation and use_deterministic_aggregation are mutually exclusive"
            )
        return self


class MiningAdapter(Protocol):
    """Abstraction for query-to-entity mining backends."""

    async def mine(self, query: str) -> MiningResult:
        """Extract intent and entities from a user query.

        Args:
            query (str): User query text.

        Returns:
            MiningResult: Structured mining output.
        """
        ...


@dataclass(slots=True)
class DeterministicMiningAdapter:
    """Test-friendly extraction adapter used until Vertex integration is added."""

    async def mine(self, query: str) -> MiningResult:
        """Extract entities from user query using deterministic heuristics.

        Args:
            query (str): User query text.

        Returns:
            MiningResult: Structured extraction result.
        """
        started = perf_counter()
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", query)
        # Preserve first occurrence order to keep trace IDs stable in tests.
        unique_tokens: list[str] = list(dict.fromkeys(token.lower() for token in tokens))

        entities = [
            MinedEntity(entity_id=f"ent_{token}", entity_type="OBJECT", confidence=0.80)
            for token in unique_tokens[:5]
        ]
        latency_ms = (perf_counter() - started) * 1000
        intent = "information_lookup" if entities else "insufficient_input"
        return MiningResult(intent=intent, entities=entities, latency_ms=latency_ms)


@dataclass(slots=True)
class VertexMiningAdapter:
    """Vertex Flash-backed mining adapter for structured entity extraction."""

    model_name: str

    async def mine(self, query: str) -> MiningResult:
        """Extract entities via Vertex Flash with schema-constrained JSON output.

        Args:
            query (str): User query text.

        Returns:
            MiningResult: Structured extraction output.

        Raises:
            MindMapPipelineError: If model invocation or parsing fails.
        """
        started = perf_counter()
        schema_instructions = (
            "Return JSON only with shape: "
            "{'intent': string, 'entities': [{'entity_id': string, 'entity_type': string, "
            "'confidence': number between 0 and 1}]}."
        )

        try:
            response_text = generate_generative_ai_text(
                self.model_name,
                f"{schema_instructions}\n\nQuery: {query}",
            )
            payload = json.loads(response_text)
            entities_payload = payload.get("entities", [])
            entities = [
                MinedEntity(
                    entity_id=item["entity_id"],
                    entity_type=item["entity_type"],
                    confidence=float(item["confidence"]),
                )
                for item in entities_payload
            ]
        except RuntimeError as error:
            if "google-generativeai" in str(error):
                raise MindMapPipelineError(
                    stage=PipelineStage.MINE,
                    code=PipelineErrorCode.MODEL_ERROR,
                    message="google-generativeai is required for vertex mining",
                ) from error
            raise
        except Exception as error:
            raise MindMapPipelineError(
                stage=PipelineStage.MINE,
                code=PipelineErrorCode.MODEL_ERROR,
                message=f"vertex mining failed: {error}",
            ) from error

        latency_ms = (perf_counter() - started) * 1000
        intent = payload.get("intent", "information_lookup")
        return MiningResult(intent=intent, entities=entities, latency_ms=latency_ms)


class AggregationAdapter(Protocol):
    """Abstraction for graph aggregation backends."""

    async def aggregate(
        self,
        *,
        mining_result: MiningResult,
        config: MindMapConfig,
    ) -> AggregationResult:
        """Aggregate mined entities into evidence graph.

        Args:
            mining_result (MiningResult): Stage 1 output.
            config (MindMapConfig): Runtime pipeline settings.

        Returns:
            AggregationResult: Evidence graph payload.
        """
        ...


class TraceRecorder(Protocol):
    """Abstraction for persisting MindMap execution traces."""

    async def record(
        self,
        *,
        trace: MindMapTrace,
        query: str,
        session_id: str | None,
        tenant_id: str | None,
        authorization_scope: AuthorizationScope | None = None,
    ) -> None:
        """Persist trace metadata for observability and audit.

        Args:
            trace (MindMapTrace): Structured pipeline trace envelope.
            query (str): Original user query.
            session_id (str | None): Session identifier if available.
            tenant_id (str | None): Tenant identifier if available.
            authorization_scope (AuthorizationScope | None): Authorization scope for the request.
        """
        ...


@dataclass(slots=True)
class NoOpTraceRecorder:
    """Trace recorder that intentionally does nothing in local/test mode."""

    async def record(
        self,
        *,
        trace: MindMapTrace,
        query: str,
        session_id: str | None,
        tenant_id: str | None,
        authorization_scope: AuthorizationScope | None = None,
    ) -> None:
        """Record trace metadata as a no-op.

        Args:
            trace (MindMapTrace): Structured pipeline trace envelope.
            query (str): Original user query.
            session_id (str | None): Session identifier if available.
            tenant_id (str | None): Tenant identifier if available.
            authorization_scope (AuthorizationScope | None): Authorization scope for the request.
        """
        del authorization_scope
        logger.debug(
            "mindmap.trace.noop",
            extra={
                "trace_id": trace.trace_id,
                "query_length": len(query),
                "session_id": session_id,
                "tenant_id": tenant_id,
            },
        )


@dataclass(slots=True)
class AuditTraceRecorder:
    """Trace recorder that writes MindMap execution metadata to Audit memory."""

    async def record(
        self,
        *,
        trace: MindMapTrace,
        query: str,
        session_id: str | None,
        tenant_id: str | None,
        authorization_scope: AuthorizationScope | None = None,
    ) -> None:
        """Persist trace metadata using Memory API audit events.

        Args:
            trace (MindMapTrace): Structured pipeline trace envelope.
            query (str): Original user query.
            session_id (str | None): Session identifier if available.
            tenant_id (str | None): Tenant identifier if available.
            authorization_scope (AuthorizationScope | None): Authorization scope for the request.

        Raises:
            MindMapPipelineError: If trace cannot be persisted.
        """
        source_node_id = session_id or trace.trace_id
        resolved_tenant_id = tenant_id or "tenant_mindmap"
        context = {
            "trace_id": trace.trace_id,
            "query": query,
            "mined_entities": trace.mined_entities,
            "path_ids": trace.path_ids,
            "fact_ids": trace.fact_ids,
            "stage_timings": [timing.model_dump(mode="json") for timing in trace.stage_timings],
        }

        try:
            await MemoryAPI.record_audit_event(
                tenant_id=resolved_tenant_id,
                event_type="MINDMAP_EXECUTION",
                source_node_id=source_node_id,
                context=context,
                authorization_scope=authorization_scope,
            )
        except RuntimeError as error:
            raise MindMapPipelineError(
                stage=PipelineStage.SYNTHESIZE,
                code=PipelineErrorCode.RETRIEVAL_ERROR,
                message=f"trace persistence failed: {error}",
            ) from error


@dataclass(slots=True)
class DeterministicAggregationAdapter:
    """Deterministic aggregation adapter for local and CI execution."""

    async def aggregate(
        self,
        *,
        mining_result: MiningResult,
        config: MindMapConfig,
    ) -> AggregationResult:
        """Generate bounded evidence graph from mined entities.

        Args:
            mining_result (MiningResult): Stage 1 output.
            config (MindMapConfig): Runtime pipeline settings.

        Returns:
            AggregationResult: Deterministic evidence graph.
        """
        started = perf_counter()
        nodes: list[EvidenceNode] = []
        edges: list[EvidenceEdge] = []
        paths: list[EvidencePath] = []

        for idx, entity in enumerate(mining_result.entities[: config.max_paths]):
            source_id = entity.entity_id
            target_id = f"ctx_{source_id}"
            edge_id = f"edge_{idx}_{source_id}"
            path_id = f"path_{idx}_{source_id}"

            nodes.append(
                EvidenceNode(
                    node_id=source_id,
                    memory_tier="SEMANTIC",
                    label=entity.entity_type,
                    weight=max(entity.confidence, config.cognitive_weight_threshold),
                )
            )
            nodes.append(
                EvidenceNode(
                    node_id=target_id,
                    memory_tier="CONTEXT",
                    label="ContextNode",
                    weight=config.cognitive_weight_threshold,
                )
            )
            edges.append(
                EvidenceEdge(
                    edge_id=edge_id,
                    source_node_id=source_id,
                    destination_node_id=target_id,
                    rel_type="RELATED_TO",
                    weight=config.cognitive_weight_threshold,
                )
            )
            paths.append(
                EvidencePath(path_id=path_id, node_ids=[source_id, target_id], edge_ids=[edge_id])
            )

        nodes = nodes[: config.max_evidence_nodes]
        latency_ms = (perf_counter() - started) * 1000
        return AggregationResult(nodes=nodes, edges=edges, paths=paths, latency_ms=latency_ms)


@dataclass(slots=True)
class SpannerAggregationAdapter:
    """Spanner-backed aggregation adapter for graph retrieval.

    This adapter intentionally uses a conservative query shape during initial Phase 2
    implementation to keep behavior predictable. It can be expanded with variable-length
    GRAPH queries as we tune performance characteristics.
    """

    async def aggregate(
        self,
        *,
        mining_result: MiningResult,
        config: MindMapConfig,
    ) -> AggregationResult:
        """Retrieve evidence graph from Spanner for mined entities.

        Args:
            mining_result (MiningResult): Stage 1 output.
            config (MindMapConfig): Runtime pipeline settings.

        Returns:
            AggregationResult: Graph evidence constrained by cognitive threshold.

        Raises:
            MindMapPipelineError: If retrieval cannot run.
        """
        started = perf_counter()
        entity_ids = [entity.entity_id for entity in mining_result.entities]
        if not entity_ids:
            latency_ms = (perf_counter() - started) * 1000
            return AggregationResult(nodes=[], edges=[], paths=[], latency_ms=latency_ms)

        max_hops = max(1, min(config.max_hops, 6))
        sql = f"""
            GRAPH MemoryGraph
            MATCH (n:MemoryNode)
                -[e:MemoryEdge*1..{max_hops}]->
                (m:MemoryNode)
            WHERE n.NodeId IN UNNEST(@entity_ids)
              AND e.LogOddsWeight >= @threshold
              AND m.MemoryTier IN ('SEMANTIC', 'CONTEXT')
            RETURN
                n.NodeId,
                n.MemoryTier,
                n.Label,
                n.LogOddsWeight,
                e.EdgeId,
                m.NodeId,
                e.RelType,
                e.LogOddsWeight
            LIMIT @max_paths
        """

        try:
            rows = SpannerClient.execute_sql(  # type: ignore[return-value]
                sql,
                params={
                    "entity_ids": entity_ids,
                    "threshold": config.cognitive_weight_threshold,
                    "max_paths": config.max_paths,
                },
            )
        except Exception as error:
            if _is_graph_query_unsupported(error):
                logger.info("graph_query_unsupported_returning_empty_aggregation")
                latency_ms = (perf_counter() - started) * 1000
                return AggregationResult(nodes=[], edges=[], paths=[], latency_ms=latency_ms)
            raise MindMapPipelineError(
                stage=PipelineStage.AGGREGATE,
                code=PipelineErrorCode.RETRIEVAL_ERROR,
                message=f"spanner retrieval unavailable: {error}",
            ) from error

        nodes: dict[str, EvidenceNode] = {}
        edges: list[EvidenceEdge] = []
        paths: list[EvidencePath] = []

        for idx, row in enumerate(rows):  # type: ignore[union-attr]
            (
                source_node_id,
                memory_tier,
                label,
                source_weight,
                edge_id,
                destination_node_id,
                rel_type,
                edge_weight,
            ) = row  # type: ignore[misc]

            if source_node_id not in nodes:  # type: ignore[operator]
                nodes[str(source_node_id)] = EvidenceNode(  # type: ignore[arg-type]
                    node_id=str(source_node_id),  # type: ignore[arg-type]
                    memory_tier=str(memory_tier),  # type: ignore[arg-type]
                    label=str(label),  # type: ignore[arg-type]
                    weight=float(source_weight) if source_weight else 0.0,  # type: ignore[arg-type]
                )

            if destination_node_id not in nodes:  # type: ignore[operator]
                nodes[str(destination_node_id)] = EvidenceNode(  # type: ignore[arg-type]
                    node_id=str(destination_node_id),  # type: ignore[arg-type]
                    memory_tier="CONTEXT",
                    label="ContextNode",
                    weight=float(edge_weight) if edge_weight else 0.0,  # type: ignore[arg-type]
                )

            edges.append(
                EvidenceEdge(
                    edge_id=str(edge_id),  # type: ignore[arg-type]
                    source_node_id=str(source_node_id),  # type: ignore[arg-type]
                    destination_node_id=str(destination_node_id),  # type: ignore[arg-type]
                    rel_type=str(rel_type),  # type: ignore[arg-type]
                    weight=float(edge_weight) if edge_weight else 0.0,  # type: ignore[arg-type]
                )
            )
            paths.append(
                EvidencePath(
                    path_id=f"path_{idx}_{source_node_id}",
                    node_ids=[str(source_node_id), str(destination_node_id)],
                    edge_ids=[str(edge_id)],
                )
            )

        bounded_nodes = list(nodes.values())[: config.max_evidence_nodes]
        latency_ms = (perf_counter() - started) * 1000
        return AggregationResult(
            nodes=bounded_nodes, edges=edges, paths=paths, latency_ms=latency_ms
        )


class MindMapPipeline:
    """Mine -> Aggregate -> Serialize -> Synthesize orchestration."""

    INSUFFICIENT_EVIDENCE_RESPONSE = "Insufficient graph evidence."
    VERTEX_SYNTHESIS_SYSTEM_PROMPT = (
        "Use ONLY the provided fact statements. If evidence is insufficient, "
        "respond exactly with: 'Insufficient graph evidence.'"
    )

    def _select_aggregation_adapter(
        self,
        aggregation_adapter: AggregationAdapter | None,
    ) -> AggregationAdapter:
        """Select aggregation adapter based on config and availability.

        Args:
            aggregation_adapter: Custom adapter provided by caller.

        Returns:
            AggregationAdapter: Selected aggregation adapter.
        """
        if aggregation_adapter is not None:
            return aggregation_adapter

        # Explicit override for deterministic aggregation
        if self.config.use_deterministic_aggregation:
            return DeterministicAggregationAdapter()

        # Backward compatibility: respect use_spanner_aggregation flag
        if self.config.use_spanner_aggregation:
            return SpannerAggregationAdapter()

        # Graph-backed aggregation is the default (Phase 4 best practice)
        # Falls back to deterministic if SpannerClient is not initialized
        try:
            SpannerClient.get_database()  # Check if initialized
            return SpannerAggregationAdapter()
        except RuntimeError:
            logger.debug("SpannerClient not initialized; falling back to deterministic aggregation")
            return DeterministicAggregationAdapter()

    def __init__(
        self,
        *,
        config: MindMapConfig | None = None,
        mining_adapter: MiningAdapter | None = None,
        aggregation_adapter: AggregationAdapter | None = None,
        trace_recorder: TraceRecorder | None = None,
        spanner_client: SpannerClient | None = None,
    ) -> None:
        """Initialize pipeline dependencies.

        Args:
            config (MindMapConfig | None, optional): Pipeline config.
                When None, uses defaults. Defaults to None.
            mining_adapter (MiningAdapter | None, optional): Mining adapter.
                When None, uses deterministic adapter. Defaults to None.
            aggregation_adapter (AggregationAdapter | None, optional): Aggregation adapter.
                When None, selects adapter from config. Defaults to None.
            trace_recorder (TraceRecorder | None, optional): Trace persistence adapter.
                When None, selects recorder from config. Defaults to None.
            spanner_client (SpannerClient | None, optional): Spanner client for evidence service.
                When None, uses singleton instance. Defaults to None.
        """
        self.config = config or MindMapConfig()
        if mining_adapter is not None:
            self.mining_adapter = mining_adapter
        elif self.config.use_vertex_mining:
            self.mining_adapter = VertexMiningAdapter(model_name=self.config.extraction_model_name)
        else:
            self.mining_adapter = DeterministicMiningAdapter()

        self.aggregation_adapter = self._select_aggregation_adapter(aggregation_adapter)

        if trace_recorder is not None:
            self.trace_recorder = trace_recorder
        elif self.config.enable_trace_recording:
            self.trace_recorder = AuditTraceRecorder()
        else:
            self.trace_recorder = NoOpTraceRecorder()

        # Phase 4E: Initialize evidence service for synthesis grounding
        if spanner_client is not None:
            self.spanner_client = spanner_client
        else:
            self.spanner_client = SpannerClient()

        # Get the Spanner client - may raise RuntimeError if not initialized
        try:
            spanner_native_client = SpannerClient.get_client()
            self.evidence_service = EvidenceService(spanner_native_client)
        except RuntimeError:
            # In test/local mode without Spanner initialized, use a mock
            logger.warning("SpannerClient not initialized; evidence service may not work")
            self.evidence_service = EvidenceService(None)  # type: ignore[arg-type]

    async def execute(
        self,
        query: str,
        session_id: str | None = None,
        tenant_id: str | None = None,
        authorization_scope: AuthorizationScope | None = None,
    ) -> MindMapResponse:
        """Run full MindMap pipeline and return grounded result.

        Args:
            query (str): User query string.
            session_id (str | None, optional): Session identifier. Defaults to None.
            tenant_id (str | None, optional): Tenant identifier for request scoping.
                Defaults to None.
            authorization_scope (AuthorizationScope | None, optional): Authorization scope
                for the request. Defaults to None.

        Returns:
            MindMapResponse: Final response with traceability envelope.

        Raises:
            MindMapPipelineError: If validation fails.
        """
        with trace_span(
            "mindmap.execute",
            attributes={
                "session.id": session_id or "",
                "tenant.id": tenant_id or "",
                "query.length": len(query),
            },
        ):
            self._validate_query(query)
            trace_id = f"trace_{uuid.uuid4()}"
            stage_timings: list[StageTiming] = []

            mining_result = await self.mining_adapter.mine(query)
            stage_timings.append(
                StageTiming(stage=PipelineStage.MINE, latency_ms=mining_result.latency_ms)
            )

            aggregation_result = await self.aggregation_adapter.aggregate(
                mining_result=mining_result,
                config=self.config,
            )
            stage_timings.append(
                StageTiming(stage=PipelineStage.AGGREGATE, latency_ms=aggregation_result.latency_ms)
            )

            serialization_result = self._serialize(aggregation_result=aggregation_result)
            stage_timings.append(
                StageTiming(
                    stage=PipelineStage.SERIALIZE, latency_ms=serialization_result.latency_ms
                )
            )

            # Phase 4E: Build evidence context for synthesis grounding
            evidence_context = None
            if tenant_id:
                try:
                    entity_ids = [entity.entity_id for entity in mining_result.entities]
                    evidence_context = await self.evidence_service.build_evidence_context(
                        tenant_id=tenant_id,
                        mined_entities=entity_ids,
                        session_id=session_id,
                    )
                    # Phase 5: Enrich evidence context with confidence and freshness
                    self.evidence_service.enrich_evidence_context_with_phase5(
                        context=evidence_context,
                        freshness_decay_lambda=self.config.freshness_decay_lambda,
                    )
                except Exception as error:  # noqa: BLE001
                    logger.warning(
                        "evidence_context.build_failed",
                        extra={"tenant_id": tenant_id, "error": str(error)},
                    )

            if self.config.use_vertex_synthesis:
                synthesis_result = self._synthesize_with_vertex(
                    serialization_result=serialization_result,
                    mining_result=mining_result,
                    tenant_id=tenant_id,
                    evidence_context=evidence_context,
                )
            else:
                synthesis_result = self._synthesize(
                    serialization_result=serialization_result,
                    mining_result=mining_result,
                    tenant_id=tenant_id,
                    evidence_context=evidence_context,
                )
            self._validate_grounding(
                synthesis_result=synthesis_result,
                serialization_result=serialization_result,
            )
            stage_timings.append(
                StageTiming(stage=PipelineStage.SYNTHESIZE, latency_ms=synthesis_result.latency_ms)
            )

            trace = MindMapTrace(
                trace_id=trace_id,
                mined_entities=[entity.entity_id for entity in mining_result.entities],
                path_ids=[path.path_id for path in aggregation_result.paths],
                fact_ids=[fact.fact_id for fact in serialization_result.facts],
                stage_timings=stage_timings,
                created_at=self._now(),
            )

            logger.info(
                "mindmap.execute.complete",
                extra={
                    "trace_id": trace_id,
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "query_length": len(query),
                    "fact_count": len(serialization_result.facts),
                    "grounded": synthesis_result.grounded,
                    "evidence_sufficient": evidence_context.is_sufficient
                    if evidence_context
                    else None,
                },
            )

            total_latency_ms = sum(t.latency_ms for t in stage_timings)
            pipeline_execution_histogram().record(
                total_latency_ms,
                {
                    "grounded": str(synthesis_result.grounded),
                    "tenant.id": tenant_id or "",
                },
            )
            pipeline_fact_counter().add(
                len(serialization_result.facts),
                {"tenant.id": tenant_id or ""},
            )

            await self.trace_recorder.record(
                trace=trace,
                query=query,
                session_id=session_id,
                tenant_id=tenant_id,
                authorization_scope=authorization_scope,
            )

            evidence_summary = None
            if evidence_context:
                evidence_summary = EvidenceSummary(
                    total_items=evidence_context.total_items,
                    path_count=evidence_context.path_count,
                    neighbor_count=evidence_context.neighbor_count,
                    is_sufficient=evidence_context.is_sufficient,
                    is_empty=evidence_context.is_empty,
                    insufficient_reasons=evidence_context.insufficient_reasons,
                    retrieval_latency_ms=evidence_context.retrieval_latency_ms,
                )

            return MindMapResponse(
                query=query,
                synthesis=synthesis_result,
                trace=trace,
                evidence_summary=evidence_summary,
            )

    def _validate_query(self, query: str) -> None:
        """Validate user query before pipeline execution.

        Args:
            query (str): User query.

        Raises:
            MindMapPipelineError: If query is empty or whitespace.
        """
        if not query.strip():
            raise MindMapPipelineError(
                stage=PipelineStage.MINE,
                code=PipelineErrorCode.VALIDATION_ERROR,
                message="query cannot be empty",
            )

    def _serialize(self, *, aggregation_result: AggregationResult) -> SerializationResult:
        """Serialize evidence graph into canonical facts.

        Args:
            aggregation_result (AggregationResult): Stage 2 output.

        Returns:
            SerializationResult: Canonical and markdown fact output.
        """
        started = perf_counter()
        facts: list[SerializedFact] = []
        edge_by_id = {edge.edge_id: edge for edge in aggregation_result.edges}

        _minimum_path_nodes = 2
        for idx, path in enumerate(aggregation_result.paths, start=1):
            if len(path.node_ids) < _minimum_path_nodes:
                continue

            primary_edge_id = path.edge_ids[0] if path.edge_ids else None
            evidence_edge = edge_by_id.get(primary_edge_id) if primary_edge_id else None
            rel_type = evidence_edge.rel_type if evidence_edge else "RELATED_TO"
            weight = (
                evidence_edge.weight if evidence_edge else self.config.cognitive_weight_threshold
            )

            statement = (
                f"FACT {idx}: ({path.node_ids[0]}) "
                f"-[{rel_type}:{weight:.2f}]-> ({path.node_ids[1]})"
            )
            facts.append(
                SerializedFact(
                    fact_id=f"fact_{idx}",
                    statement=statement,
                    path_id=path.path_id,
                    edge_ids=path.edge_ids,
                    rel_type=rel_type,
                    weight=weight,
                )
            )

        markdown = "\n".join(fact.statement for fact in facts)
        latency_ms = (perf_counter() - started) * 1000
        return SerializationResult(facts=facts, markdown=markdown, latency_ms=latency_ms)

    def _synthesize(
        self,
        *,
        serialization_result: SerializationResult,
        mining_result: MiningResult,
        tenant_id: str | None = None,
        evidence_context: EvidenceContext | None = None,
    ) -> SynthesisResult:
        """Create final answer strictly from serialized facts.

        Args:
            serialization_result (SerializationResult): Stage 3 output.
            mining_result (MiningResult): Mined entities from query.
            tenant_id (str | None): Tenant identifier.
            evidence_context (object | None): Evidence context with sufficiency signals.

        Returns:
            SynthesisResult: Grounded user response.
        """
        del mining_result, tenant_id  # Unused in deterministic mode
        started = perf_counter()
        signal = self._build_phase5_synthesis_signal(evidence_context=evidence_context)

        if not serialization_result.facts:
            return SynthesisResult(
                response_text=self.INSUFFICIENT_EVIDENCE_RESPONSE,
                claim_fact_ids=[],
                grounded=True,
                latency_ms=(perf_counter() - started) * 1000,
                confidence_score=signal.response_confidence_score if signal else 1.0,
                contradiction_warnings=[
                    warning.model_dump(mode="json") for warning in signal.contradiction_warnings
                ]
                if signal
                else [],
                confidence_signal=signal,
            )

        if signal and signal.gating_applied == "hard_reject":
            return SynthesisResult(
                response_text=self.INSUFFICIENT_EVIDENCE_RESPONSE,
                claim_fact_ids=[],
                grounded=True,
                latency_ms=(perf_counter() - started) * 1000,
                confidence_score=signal.response_confidence_score,
                contradiction_warnings=[
                    warning.model_dump(mode="json") for warning in signal.contradiction_warnings
                ],
                confidence_signal=signal,
            )

        # Phase 4E: Annotate response with evidence sufficiency
        response_lines = ["Grounded summary:"]
        response_lines.extend(f"- {fact.statement}" for fact in serialization_result.facts)

        if evidence_context and not evidence_context.is_sufficient:
            caveat = (
                "\n⚠️  Evidence insufficiency: "
                f"{', '.join(str(r) for r in evidence_context.insufficient_reasons)} "
                f"({evidence_context.total_items} items retrieved)"
            )
            response_lines.append(caveat)

        if signal and signal.gating_applied == "soft_signal":
            response_lines.append("")
            response_lines.append("⚠️  Phase 5 confidence signal:")
            response_lines.append(f"- response confidence: {signal.response_confidence_score:.2f}")
            response_lines.append(
                "- evidence confidence: "
                f"avg {signal.evidence_confidence_breakdown.average_confidence:.2f}, "
                f"min {signal.evidence_confidence_breakdown.min_confidence:.2f}"
            )
            if signal.contradiction_warnings:
                warning_text = "; ".join(
                    warning.description or ", ".join(warning.conflicting_node_ids)
                    for warning in signal.contradiction_warnings
                )
                response_lines.append(f"- contradictions: {warning_text}")
            if signal.gating_reason:
                response_lines.append(f"- gating reason: {signal.gating_reason}")

        return SynthesisResult(
            response_text="\n".join(response_lines),
            claim_fact_ids=[fact.fact_id for fact in serialization_result.facts],
            grounded=True,
            latency_ms=(perf_counter() - started) * 1000,
            confidence_score=signal.response_confidence_score if signal else 1.0,
            contradiction_warnings=[
                warning.model_dump(mode="json") for warning in signal.contradiction_warnings
            ]
            if signal
            else [],
            confidence_signal=signal,
        )

    def _build_phase5_synthesis_signal(
        self,
        evidence_context: EvidenceContext | None,
    ) -> SynthesisConfidenceSignal | None:
        """Build a typed Phase 5 confidence signal from evidence context.

        Args:
            evidence_context: Evidence context returned from retrieval.

        Returns:
            A synthesis confidence signal when evidence context is available, otherwise None.
        """
        if evidence_context is None:
            return None

        confidence_scores = [item.source_confidence_score for item in evidence_context.items]
        breakdown = ConfidenceBreakdown.from_scores(confidence_scores)
        contradiction_warnings = self._build_phase5_contradiction_warnings(evidence_context)
        freshness_values = [
            item.freshness_score
            for item in evidence_context.items
            if item.freshness_score is not None
        ]
        freshness_range = (
            (min(freshness_values), max(freshness_values)) if freshness_values else (0.0, 0.0)
        )
        average_freshness = (
            sum(freshness_values) / len(freshness_values) if freshness_values else 0.0
        )

        response_confidence_score = breakdown.average_confidence
        if contradiction_warnings and self.config.enable_contradiction_detection:
            gating_cfg = self.config.gating
            penalty = min(
                gating_cfg.max_total_penalty,
                gating_cfg.per_contradiction_penalty * len(contradiction_warnings),
            )
            if any(
                warning.severity == ContradictionSeverity.HIGH for warning in contradiction_warnings
            ):
                penalty = min(
                    gating_cfg.max_total_penalty,
                    penalty + gating_cfg.high_severity_bonus_penalty,
                )
            response_confidence_score = max(0.0, response_confidence_score - penalty)

        # Check gating conditions: confidence, freshness, or contradictions
        confidence_below_threshold = response_confidence_score < self.config.confidence_threshold
        freshness_below_threshold = (
            average_freshness < self.config.freshness_threshold
            and self.config.freshness_threshold > 0.0
        )
        has_contradictions = contradiction_warnings and self.config.enable_contradiction_detection

        if (
            confidence_below_threshold
            or freshness_below_threshold
            or (has_contradictions and self.config.synthesis_gating_mode == "hard_reject")
        ):
            gating_applied = self.config.synthesis_gating_mode
            gating_reason_parts = [
                (
                    f"confidence {response_confidence_score:.2f} below threshold "
                    f"{self.config.confidence_threshold:.2f}"
                    if confidence_below_threshold
                    else ""
                ),
                (
                    f"freshness {average_freshness:.2f} below threshold "
                    f"{self.config.freshness_threshold:.2f}"
                    if freshness_below_threshold
                    else ""
                ),
                (
                    f"{len(contradiction_warnings)} contradiction warning(s) detected"
                    if has_contradictions
                    else ""
                ),
            ]
            gating_reason = "; ".join(reason for reason in gating_reason_parts if reason)
        elif has_contradictions:
            gating_applied = "soft_signal"
            gating_reason = f"{len(contradiction_warnings)} contradiction warning(s) detected"
        else:
            gating_applied = "none"
            gating_reason = ""

        return SynthesisConfidenceSignal(
            response_confidence_score=response_confidence_score,
            evidence_confidence_breakdown=breakdown,
            freshness_range=freshness_range,
            contradiction_warnings=contradiction_warnings,
            gating_applied=gating_applied,
            gating_reason=gating_reason,
        )

    def _build_phase5_contradiction_warnings(
        self,
        evidence_context: EvidenceContext,
    ) -> list[ContradictionWarning]:
        """Convert evidence-level contradiction groups into typed warnings."""
        contradictions_by_severity: dict[str, set[str]] = {
            "high": set(),
            "medium": set(),
            "low": set(),
        }

        for item in evidence_context.items:
            for flag_str in item.contradiction_flags:
                if ":" in flag_str:
                    severity, node_id = flag_str.split(":", 1)
                    if severity in contradictions_by_severity:
                        contradictions_by_severity[severity].add(node_id)
                else:
                    contradictions_by_severity["medium"].add(flag_str)

        warnings: list[ContradictionWarning] = []
        for severity in ["high", "medium", "low"]:
            nodes = contradictions_by_severity[severity]
            if not nodes:
                continue
            warnings.append(
                ContradictionWarning(
                    conflicting_node_ids=sorted(nodes),
                    detected_by="evidence_service",
                    severity=ContradictionSeverity(severity),
                    description=f"{len(nodes)} conflicting node(s) detected",
                )
            )

        return warnings

    def _validate_grounding(
        self,
        *,
        synthesis_result: SynthesisResult,
        serialization_result: SerializationResult,
    ) -> None:
        """Ensure all synthesized claims map to serialized evidence facts.

        Args:
            synthesis_result (SynthesisResult): Synthesis stage output.
            serialization_result (SerializationResult): Serialized fact payload.

        Raises:
            MindMapPipelineError: If any claim references a non-existing fact.
        """
        valid_fact_ids = {fact.fact_id for fact in serialization_result.facts}
        missing_ids = [
            fact_id for fact_id in synthesis_result.claim_fact_ids if fact_id not in valid_fact_ids
        ]

        if missing_ids:
            raise MindMapPipelineError(
                stage=PipelineStage.SYNTHESIZE,
                code=PipelineErrorCode.GROUNDING_ERROR,
                message=f"ungrounded claims detected: {missing_ids}",
            )

    def _synthesize_with_vertex(
        self,
        *,
        serialization_result: SerializationResult,
        mining_result: MiningResult,
        tenant_id: str | None = None,
        evidence_context: EvidenceContext | None = None,
    ) -> SynthesisResult:
        """Generate synthesis using Vertex Pro under strict grounding instructions.

        Args:
            serialization_result (SerializationResult): Serialized evidence payload.
            mining_result (MiningResult): Mined entities from query.
            tenant_id (str | None): Tenant identifier.
            evidence_context (object | None): Evidence context with sufficiency signals.

        Returns:
            SynthesisResult: Model-generated synthesis constrained to evidence.

        Raises:
            MindMapPipelineError: If model invocation fails.
        """
        del mining_result, tenant_id  # Unused in synthesis
        started = perf_counter()
        signal = self._build_phase5_synthesis_signal(evidence_context=evidence_context)
        if not serialization_result.facts:
            return SynthesisResult(
                response_text=self.INSUFFICIENT_EVIDENCE_RESPONSE,
                claim_fact_ids=[],
                grounded=True,
                latency_ms=(perf_counter() - started) * 1000,
                confidence_score=signal.response_confidence_score if signal else 1.0,
                contradiction_warnings=[
                    warning.model_dump(mode="json") for warning in signal.contradiction_warnings
                ]
                if signal
                else [],
                confidence_signal=signal,
            )

        if signal and signal.gating_applied == "hard_reject":
            return SynthesisResult(
                response_text=self.INSUFFICIENT_EVIDENCE_RESPONSE,
                claim_fact_ids=[],
                grounded=True,
                latency_ms=(perf_counter() - started) * 1000,
                confidence_score=signal.response_confidence_score,
                contradiction_warnings=[
                    warning.model_dump(mode="json") for warning in signal.contradiction_warnings
                ],
                confidence_signal=signal,
            )

        # Phase 4E: Annotate synthesis prompt with evidence metadata
        evidence_annotation = ""
        if evidence_context:
            is_sufficient = evidence_context.is_sufficient
            evidence_annotation = (
                f"\n\nEvidence Quality Signals:\n"
                f"- Total evidence items: {evidence_context.total_items}\n"
                f"- Path-based evidence: {evidence_context.path_count}\n"
                f"- Neighbor-based evidence: {evidence_context.neighbor_count}\n"
                f"- Evidence sufficient: {is_sufficient}\n"
            )
            if signal is not None:
                evidence_annotation += (
                    f"- Response confidence: {signal.response_confidence_score:.2f}\n"
                    f"- Confidence threshold: {self.config.confidence_threshold:.2f}\n"
                )
            if not is_sufficient:
                insufficient_reasons_str = ", ".join(
                    str(r) for r in evidence_context.insufficient_reasons
                )
                evidence_annotation += f"- Insufficiency reasons: {insufficient_reasons_str}\n"
                evidence_annotation += (
                    "⚠️  ALERT: Evidence is insufficient for high-confidence synthesis. "
                    "If responding, append disclaimer.\n"
                )
            if signal and signal.contradiction_warnings:
                contradiction_text = "; ".join(
                    warning.description for warning in signal.contradiction_warnings
                )
                evidence_annotation += f"- Contradiction warnings: {contradiction_text}\n"

        prompt = (
            f"{self.VERTEX_SYNTHESIS_SYSTEM_PROMPT}{evidence_annotation}"
            f"\n\nFacts:\n{serialization_result.markdown}"
        )

        try:
            response_text = generate_generative_ai_text(
                self.config.synthesis_model_name,
                prompt,
            ).strip()
        except RuntimeError as error:
            if "google-generativeai" in str(error):
                raise MindMapPipelineError(
                    stage=PipelineStage.SYNTHESIZE,
                    code=PipelineErrorCode.MODEL_ERROR,
                    message="google-generativeai is required for vertex synthesis",
                ) from error
            raise
        except Exception as error:
            raise MindMapPipelineError(
                stage=PipelineStage.SYNTHESIZE,
                code=PipelineErrorCode.MODEL_ERROR,
                message=f"vertex synthesis failed: {error}",
            ) from error

        if response_text == self.INSUFFICIENT_EVIDENCE_RESPONSE:
            claim_fact_ids: list[str] = []
        else:
            claim_fact_ids = [fact.fact_id for fact in serialization_result.facts]

        return SynthesisResult(
            response_text=response_text or self.INSUFFICIENT_EVIDENCE_RESPONSE,
            claim_fact_ids=claim_fact_ids,
            grounded=True,
            latency_ms=(perf_counter() - started) * 1000,
            confidence_score=signal.response_confidence_score if signal else 1.0,
            contradiction_warnings=[
                warning.model_dump(mode="json") for warning in signal.contradiction_warnings
            ]
            if signal
            else [],
            confidence_signal=signal,
        )

    @staticmethod
    def _now() -> datetime:
        """Return current UTC timestamp.

        Returns:
            datetime: Current UTC timestamp.
        """
        return datetime.now(tz=UTC)
