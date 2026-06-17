"""MindMap query pipeline implementation scaffold for Phase 2."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol

from pydantic import BaseModel, Field

from src.db.spanner_client import SpannerClient
from src.memory.api import MemoryAPI
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

logger = logging.getLogger(__name__)


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


class MindMapConfig(BaseModel):
    """Runtime configuration for MindMap execution."""

    cognitive_weight_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    max_hops: int = Field(default=3, ge=1, le=6)
    max_paths: int = Field(default=20, ge=1)
    max_evidence_nodes: int = Field(default=200, ge=1)
    extraction_model_name: str = Field(default="gemini-2.5-flash")
    synthesis_model_name: str = Field(default="gemini-2.5-pro")
    use_spanner_aggregation: bool = Field(default=False)
    enable_trace_recording: bool = Field(default=False)


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


class TraceRecorder(Protocol):
    """Abstraction for persisting MindMap execution traces."""

    async def record(self, *, trace: MindMapTrace, query: str, session_id: str | None) -> None:
        """Persist trace metadata for observability and audit.

        Args:
            trace (MindMapTrace): Structured pipeline trace envelope.
            query (str): Original user query.
            session_id (str | None): Session identifier if available.
        """


@dataclass(slots=True)
class NoOpTraceRecorder:
    """Trace recorder that intentionally does nothing in local/test mode."""

    async def record(self, *, trace: MindMapTrace, query: str, session_id: str | None) -> None:
        """Record trace metadata as a no-op.

        Args:
            trace (MindMapTrace): Structured pipeline trace envelope.
            query (str): Original user query.
            session_id (str | None): Session identifier if available.
        """
        logger.debug(
            "mindmap.trace.noop",
            extra={
                "trace_id": trace.trace_id,
                "query_length": len(query),
                "session_id": session_id,
            },
        )


@dataclass(slots=True)
class AuditTraceRecorder:
    """Trace recorder that writes MindMap execution metadata to Audit memory."""

    async def record(self, *, trace: MindMapTrace, query: str, session_id: str | None) -> None:
        """Persist trace metadata using Memory API audit events.

        Args:
            trace (MindMapTrace): Structured pipeline trace envelope.
            query (str): Original user query.
            session_id (str | None): Session identifier if available.

        Raises:
            MindMapPipelineError: If trace cannot be persisted.
        """
        source_node_id = session_id or trace.trace_id
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
                event_type="MINDMAP_EXECUTION",
                source_node_id=source_node_id,
                context=context,
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

        sql = """
            SELECT
                n.NodeId,
                n.MemoryTier,
                n.Label,
                n.LogOddsWeight,
                e.EdgeId,
                e.DestNodeId,
                e.RelType,
                e.LogOddsWeight
            FROM MemoryNode AS n
            JOIN MemoryEdge AS e ON e.SourceNodeId = n.NodeId
            WHERE n.NodeId IN UNNEST(@entity_ids)
              AND e.LogOddsWeight >= @threshold
            LIMIT @max_paths
        """

        try:
            rows = SpannerClient.execute_sql(
                sql,
                params={
                    "entity_ids": entity_ids,
                    "threshold": config.cognitive_weight_threshold,
                    "max_paths": config.max_paths,
                },
            )
        except RuntimeError as error:
            raise MindMapPipelineError(
                stage=PipelineStage.AGGREGATE,
                code=PipelineErrorCode.RETRIEVAL_ERROR,
                message=f"spanner retrieval unavailable: {error}",
            ) from error

        nodes: dict[str, EvidenceNode] = {}
        edges: list[EvidenceEdge] = []
        paths: list[EvidencePath] = []

        for idx, row in enumerate(rows):
            (
                source_node_id,
                memory_tier,
                label,
                source_weight,
                edge_id,
                destination_node_id,
                rel_type,
                edge_weight,
            ) = row

            if source_node_id not in nodes:
                nodes[source_node_id] = EvidenceNode(
                    node_id=source_node_id,
                    memory_tier=memory_tier,
                    label=label,
                    weight=source_weight,
                )

            if destination_node_id not in nodes:
                nodes[destination_node_id] = EvidenceNode(
                    node_id=destination_node_id,
                    memory_tier="CONTEXT",
                    label="ContextNode",
                    weight=edge_weight,
                )

            edges.append(
                EvidenceEdge(
                    edge_id=edge_id,
                    source_node_id=source_node_id,
                    destination_node_id=destination_node_id,
                    rel_type=rel_type,
                    weight=edge_weight,
                )
            )
            paths.append(
                EvidencePath(
                    path_id=f"path_{idx}_{source_node_id}",
                    node_ids=[source_node_id, destination_node_id],
                    edge_ids=[edge_id],
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

    def __init__(
        self,
        *,
        config: MindMapConfig | None = None,
        mining_adapter: DeterministicMiningAdapter | None = None,
        aggregation_adapter: AggregationAdapter | None = None,
        trace_recorder: TraceRecorder | None = None,
    ) -> None:
        """Initialize pipeline dependencies.

        Args:
            config (MindMapConfig | None, optional): Pipeline config.
                When None, uses defaults. Defaults to None.
            mining_adapter (DeterministicMiningAdapter | None, optional): Mining adapter.
                When None, uses deterministic adapter. Defaults to None.
            aggregation_adapter (AggregationAdapter | None, optional): Aggregation adapter.
                When None, selects adapter from config. Defaults to None.
            trace_recorder (TraceRecorder | None, optional): Trace persistence adapter.
                When None, selects recorder from config. Defaults to None.
        """
        self.config = config or MindMapConfig()
        self.mining_adapter = mining_adapter or DeterministicMiningAdapter()
        if aggregation_adapter is not None:
            self.aggregation_adapter = aggregation_adapter
        elif self.config.use_spanner_aggregation:
            self.aggregation_adapter = SpannerAggregationAdapter()
        else:
            self.aggregation_adapter = DeterministicAggregationAdapter()

        if trace_recorder is not None:
            self.trace_recorder = trace_recorder
        elif self.config.enable_trace_recording:
            self.trace_recorder = AuditTraceRecorder()
        else:
            self.trace_recorder = NoOpTraceRecorder()

    async def execute(self, query: str, session_id: str | None = None) -> MindMapResponse:
        """Run full MindMap pipeline and return grounded result.

        Args:
            query (str): User query string.
            session_id (str | None, optional): Session identifier. Defaults to None.

        Returns:
            MindMapResponse: Final response with traceability envelope.

        Raises:
            MindMapPipelineError: If validation fails.
        """
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
            StageTiming(stage=PipelineStage.SERIALIZE, latency_ms=serialization_result.latency_ms)
        )

        synthesis_result = self._synthesize(serialization_result=serialization_result)
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
                "session_id": session_id,
                "query_length": len(query),
                "fact_count": len(serialization_result.facts),
                "grounded": synthesis_result.grounded,
            },
        )

        await self.trace_recorder.record(trace=trace, query=query, session_id=session_id)

        return MindMapResponse(query=query, synthesis=synthesis_result, trace=trace)

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

        _minimum_path_nodes = 2
        for idx, path in enumerate(aggregation_result.paths, start=1):
            if len(path.node_ids) < _minimum_path_nodes:
                continue

            statement = f"FACT {idx}: ({path.node_ids[0]}) -[RELATED_TO]-> ({path.node_ids[1]})"
            facts.append(
                SerializedFact(
                    fact_id=f"fact_{idx}",
                    statement=statement,
                    path_id=path.path_id,
                    edge_ids=path.edge_ids,
                )
            )

        markdown = "\n".join(fact.statement for fact in facts)
        latency_ms = (perf_counter() - started) * 1000
        return SerializationResult(facts=facts, markdown=markdown, latency_ms=latency_ms)

    def _synthesize(self, *, serialization_result: SerializationResult) -> SynthesisResult:
        """Create final answer strictly from serialized facts.

        Args:
            serialization_result (SerializationResult): Stage 3 output.

        Returns:
            SynthesisResult: Grounded user response.
        """
        started = perf_counter()

        if not serialization_result.facts:
            return SynthesisResult(
                response_text=self.INSUFFICIENT_EVIDENCE_RESPONSE,
                claim_fact_ids=[],
                grounded=True,
                latency_ms=(perf_counter() - started) * 1000,
            )

        response_lines = ["Grounded summary:"]
        response_lines.extend(f"- {fact.statement}" for fact in serialization_result.facts)

        return SynthesisResult(
            response_text="\n".join(response_lines),
            claim_fact_ids=[fact.fact_id for fact in serialization_result.facts],
            grounded=True,
            latency_ms=(perf_counter() - started) * 1000,
        )

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

    @staticmethod
    def _now() -> datetime:
        """Return current UTC timestamp.

        Returns:
            datetime: Current UTC timestamp.
        """
        return datetime.now(tz=UTC)
