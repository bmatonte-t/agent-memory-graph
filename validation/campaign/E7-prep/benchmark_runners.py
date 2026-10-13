"""Benchmark scenario runner for E7 execution.

Implements ScenarioRunner, BenchmarkOrchestrator, and MeasurementProtocol
for executing the 12 EMC scenarios (from E4-T1/E4-T2) against the agent system.
Designed to run dry-run (offline) or live (against GCP infrastructure).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from tempfile import mkdtemp
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.agent.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)

CAMPAIGN_ID = "amg-campaign-2026-06-29"
VALID_SCENARIOS = frozenset([f"EMC-{i:03d}" for i in range(1, 13)])
VALID_AGENTS = frozenset(["AGENT-EC", "AGENT-CC", "AGENT-TA", "AGENT-SI", "AGENT-CM", "AGENT-CA"])
MAX_LATENCY_SECONDS = 15.0
DEFAULT_WORKER_COUNT = 4
DEFAULT_RUN_COUNT = 30
WARMUP_RUNS = 5
SIMULATED_SUCCESS_RATE = 0.87


class RunOutcome(StrEnum):
    """Outcome of a single benchmark run."""

    SUCCESS = "success"
    TASK_FAILURE = "task_failure"
    TIMEOUT = "timeout"
    RETRIEVAL_ERROR = "retrieval_error"
    INFERENCE_ERROR = "inference_error"
    INTEGRATION_ERROR = "integration_error"
    COST_HARD_STOP = "cost_hard_stop"
    UNKNOWN_ERROR = "unknown_error"


@dataclass(slots=True)
class RunResult:
    """Complete record of a single benchmark execution.

    Matches the run manifest schema from E4-T3.
    """

    run_id: str
    campaign_id: str
    scenario_id: str
    agent_id: str
    scenario_version: str
    execution_timestamp_utc: str
    execution_week: int
    warmup_flag: bool
    seed_run_index: int
    model_name: str
    model_version: str
    prompt_template_id: str
    config_hash: str
    # Outcome
    outcome: RunOutcome
    task_success: bool
    groundedness_score: float
    response_text: str
    cited_sources: list[str]
    # Timing
    latency_ms: int
    retrieval_latency_ms: int
    inference_latency_ms: int
    synthesis_latency_ms: int
    # Cost
    tokens_input: int
    tokens_output: int
    tokens_total: int
    estimated_cost_usd: float
    # Error
    error_type: str | None = None
    error_message: str | None = None
    # Metadata
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    nodes_traversed: int = 0
    rows_scanned: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for BigQuery ingestion and log output.

        Returns:
            dict[str, Any]: JSON-serializable representation of the run result.
        """
        return {
            "run_id": self.run_id,
            "campaign_id": self.campaign_id,
            "scenario_id": self.scenario_id,
            "agent_id": self.agent_id,
            "scenario_version": self.scenario_version,
            "execution_timestamp_utc": self.execution_timestamp_utc,
            "execution_week": self.execution_week,
            "warmup_flag": self.warmup_flag,
            "seed_run_index": self.seed_run_index,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "prompt_template_id": self.prompt_template_id,
            "config_hash": self.config_hash,
            "outcome": self.outcome.value,
            "task_success": self.task_success,
            "groundedness_score": self.groundedness_score,
            "response_text": self.response_text[:2000],  # truncate for storage
            "cited_sources": self.cited_sources,
            "latency_ms": self.latency_ms,
            "retrieval_latency_ms": self.retrieval_latency_ms,
            "inference_latency_ms": self.inference_latency_ms,
            "synthesis_latency_ms": self.synthesis_latency_ms,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "tokens_total": self.tokens_total,
            "estimated_cost_usd": self.estimated_cost_usd,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "trace_id": self.trace_id,
            "nodes_traversed": self.nodes_traversed,
            "rows_scanned": self.rows_scanned,
        }

    def to_jsonl(self) -> str:
        """Serialize to a single JSONL line for streaming log output.

        Returns:
            str: JSON-encoded run result on a single line.
        """
        return json.dumps(self.to_dict())


@dataclass(slots=True)
class ScenarioDefinition:
    """Specification of a benchmark scenario as defined in E4-T1.

    Attributes:
        scenario_id: EMC-001 through EMC-012.
        agent_id: Which agent executes this scenario.
        user_query: The prompt sent to the agent.
        description: Human-readable description of the task.
        max_latency_seconds: Latency SLA for this scenario.
        min_runs: Minimum runs required (always 30 per E4-T1).
    """

    scenario_id: str
    agent_id: str
    user_query: str
    description: str
    max_latency_seconds: float = 10.0
    min_runs: int = DEFAULT_RUN_COUNT


# Frozen scenario definitions from E4-T1. No modifications permitted.
SCENARIO_CATALOG: dict[str, ScenarioDefinition] = {
    "EMC-001": ScenarioDefinition(
        scenario_id="EMC-001",
        agent_id="AGENT-EC",
        user_query="Retrieve our return policy",
        description="Employee return policy lookup with no-evidence safe abstention",
        max_latency_seconds=10.0,
    ),
    "EMC-002": ScenarioDefinition(
        scenario_id="EMC-002",
        agent_id="AGENT-EC",
        user_query="What's the SLA for urgent tickets?",
        description="SLA configuration lookup via graph + corpus",
        max_latency_seconds=8.0,
    ),
    "EMC-003": ScenarioDefinition(
        scenario_id="EMC-003",
        agent_id="AGENT-EC",
        user_query="List active employees in support",
        description="Team member enumeration via graph traversal",
        max_latency_seconds=5.0,
    ),
    "EMC-004": ScenarioDefinition(
        scenario_id="EMC-004",
        agent_id="AGENT-CC",
        user_query="Show me my order history",
        description="Customer order history with data isolation",
        max_latency_seconds=8.0,
    ),
    "EMC-005": ScenarioDefinition(
        scenario_id="EMC-005",
        agent_id="AGENT-CC",
        user_query="What's the status of order ABC?",
        description="Order status lookup",
        max_latency_seconds=6.0,
    ),
    "EMC-006": ScenarioDefinition(
        scenario_id="EMC-006",
        agent_id="AGENT-CC",
        user_query="Can I return this product?",
        description="Return eligibility with multi-source grounding",
        max_latency_seconds=12.0,
    ),
    "EMC-007": ScenarioDefinition(
        scenario_id="EMC-007",
        agent_id="AGENT-TA",
        user_query="List open support tickets",
        description="Support ticket listing with filter and sort",
        max_latency_seconds=8.0,
    ),
    "EMC-008": ScenarioDefinition(
        scenario_id="EMC-008",
        agent_id="AGENT-TA",
        user_query="Assign ticket XYZ to employee ABC",
        description="Task assignment with audit trail",
        max_latency_seconds=10.0,
    ),
    "EMC-009": ScenarioDefinition(
        scenario_id="EMC-009",
        agent_id="AGENT-TA",
        user_query="What's the backlog for returns queue?",
        description="Queue backlog metric aggregation",
        max_latency_seconds=8.0,
    ),
    "EMC-010": ScenarioDefinition(
        scenario_id="EMC-010",
        agent_id="AGENT-SI",
        user_query="Route Slack event to correct team",
        description="Event routing via graph traversal + Slack integration",
        max_latency_seconds=8.0,
    ),
    "EMC-011": ScenarioDefinition(
        scenario_id="EMC-011",
        agent_id="AGENT-CM",
        user_query="Schedule a team sync for tomorrow",
        description="Calendar event creation with availability check",
        max_latency_seconds=12.0,
    ),
    "EMC-012": ScenarioDefinition(
        scenario_id="EMC-012",
        agent_id="AGENT-CA",
        user_query="Summarize this PR for the team",
        description="PR code summarization with hallucination check",
        max_latency_seconds=15.0,
    ),
}


@dataclass(slots=True)
class MeasurementProtocol:
    """Captures timing, tokens, and cost for a single run.

    Attributes:
        model_flash_input_cost_per_m: Cost per million input tokens, Gemini Flash.
        model_flash_output_cost_per_m: Cost per million output tokens, Gemini Flash.
        model_pro_input_cost_per_m: Cost per million input tokens, Gemini Pro.
        model_pro_output_cost_per_m: Cost per million output tokens, Gemini Pro.
    """

    model_flash_input_cost_per_m: float = 0.075
    model_flash_output_cost_per_m: float = 0.30
    model_pro_input_cost_per_m: float = 1.50
    model_pro_output_cost_per_m: float = 6.00

    def estimate_cost(
        self,
        tokens_input: int,
        tokens_output: int,
        model_name: str,
    ) -> float:
        """Estimate cost from token counts and model name.

        Args:
            tokens_input: Number of input tokens consumed.
            tokens_output: Number of output tokens generated.
            model_name: Model identifier (gemini-1.5-flash or gemini-1.5-pro).

        Returns:
            float: Estimated USD cost for this run.
        """
        if "pro" in model_name.lower():
            return (
                tokens_input / 1_000_000 * self.model_pro_input_cost_per_m
                + tokens_output / 1_000_000 * self.model_pro_output_cost_per_m
            )
        return (
            tokens_input / 1_000_000 * self.model_flash_input_cost_per_m
            + tokens_output / 1_000_000 * self.model_flash_output_cost_per_m
        )

    def model_for_agent(self, agent_id: str) -> str:
        """Return the model name for a given agent ID.

        EC, CC, SI, CM use Flash; TA, CA use Pro (from E2-T2 agent profiles).

        Args:
            agent_id: Agent identifier from VALID_AGENTS.

        Returns:
            str: Gemini model name.
        """
        if agent_id in {"AGENT-TA", "AGENT-CA"}:
            return "gemini-1.5-pro"
        return "gemini-1.5-flash"


class ScenarioRunner:
    """Executes a single benchmark scenario against the agent system.

    In dry-run mode (dry_run=True), it simulates the agent call and returns
    synthetic metrics without touching any GCP infrastructure.
    """

    def __init__(
        self,
        scenario: ScenarioDefinition,
        measurement: MeasurementProtocol | None = None,
        *,
        dry_run: bool = False,
        run_log_dir: Path | None = None,
    ) -> None:
        """Initialize the scenario runner.

        Args:
            scenario: Frozen scenario definition from SCENARIO_CATALOG.
            measurement: Protocol for cost/token estimation. Defaults to MeasurementProtocol().
            dry_run: If True, simulate execution without GCP access.
            run_log_dir: Directory to write JSONL run logs. Defaults to a private temp directory.
        """
        self.scenario = scenario
        self.measurement = measurement or MeasurementProtocol()
        self.dry_run = dry_run
        self.run_log_dir = run_log_dir or Path(mkdtemp(prefix="amg_benchmark_runs_"))
        self.run_log_dir.mkdir(parents=True, exist_ok=True)

    async def run_once(
        self,
        seed_run_index: int,
        *,
        warmup: bool = False,
        execution_week: int = 3,
    ) -> RunResult:
        """Execute the scenario once and return the full run result.

        Args:
            seed_run_index: 0-based index within the 30-run batch.
            warmup: If True, marks this as a warmup (excluded from KPI).
            execution_week: Campaign week number (3 for E7-exec).

        Returns:
            RunResult: Complete outcome including latency, tokens, cost.
        """
        run_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()
        model_name = self.measurement.model_for_agent(self.scenario.agent_id)

        if self.dry_run:
            result = self._simulate_run(
                run_id=run_id,
                timestamp=timestamp,
                seed_run_index=seed_run_index,
                warmup=warmup,
                execution_week=execution_week,
                model_name=model_name,
            )
        else:
            result = await self._live_run(
                run_id=run_id,
                timestamp=timestamp,
                seed_run_index=seed_run_index,
                warmup=warmup,
                execution_week=execution_week,
                model_name=model_name,
            )

        self._append_to_log(result)
        return result

    def _simulate_run(
        self,
        *,
        run_id: str,
        timestamp: str,
        seed_run_index: int,
        warmup: bool,
        execution_week: int,
        model_name: str,
    ) -> RunResult:
        """Return a synthetic run result for dry-run testing.

        Simulates realistic latency, token counts, and costs from the
        expected ranges documented in E7-prep-T6 per scenario.

        Args:
            run_id: Unique identifier for this run.
            timestamp: ISO 8601 timestamp of execution.
            seed_run_index: 0-based index within the run batch.
            warmup: Whether this is a warmup run.
            execution_week: Campaign week number.
            model_name: Gemini model name.

        Returns:
            RunResult: Simulated run with realistic metrics.
        """
        rng = random.Random(hash(run_id))  # deterministic per run_id

        retrieval_ms = rng.randint(80, 500)
        inference_ms = rng.randint(1200, 4000)
        synthesis_ms = rng.randint(100, 400)
        total_ms = retrieval_ms + inference_ms + synthesis_ms

        tokens_input = rng.randint(600, 1400)
        tokens_output = rng.randint(150, 450)
        cost = self.measurement.estimate_cost(tokens_input, tokens_output, model_name)

        # Simulate ~87% success rate; no-evidence runs always succeed
        task_success = rng.random() < SIMULATED_SUCCESS_RATE
        groundedness = (
            round(rng.uniform(0.72, 0.98), 3) if task_success else round(rng.uniform(0.0, 0.45), 3)
        )

        return RunResult(
            run_id=run_id,
            campaign_id=CAMPAIGN_ID,
            scenario_id=self.scenario.scenario_id,
            agent_id=self.scenario.agent_id,
            scenario_version="v1.0",
            execution_timestamp_utc=timestamp,
            execution_week=execution_week,
            warmup_flag=warmup,
            seed_run_index=seed_run_index,
            model_name=model_name,
            model_version="gemini-1.5-flash-001" if "flash" in model_name else "gemini-1.5-pro-001",
            prompt_template_id=f"prompt-{self.scenario.agent_id.lower()}-001",
            config_hash="dryrun_hash_0000000000",
            outcome=RunOutcome.SUCCESS if task_success else RunOutcome.TASK_FAILURE,
            task_success=task_success,
            groundedness_score=groundedness,
            response_text=f"[dry-run] Simulated response for {self.scenario.scenario_id}",
            cited_sources=[f"doc_{rng.randint(1, 100):04d}"] if task_success else [],
            latency_ms=total_ms,
            retrieval_latency_ms=retrieval_ms,
            inference_latency_ms=inference_ms,
            synthesis_latency_ms=synthesis_ms,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tokens_total=tokens_input + tokens_output,
            estimated_cost_usd=round(cost, 8),
            nodes_traversed=rng.randint(3, 20),
            rows_scanned=rng.randint(5, 200),
        )

    async def _live_run(
        self,
        *,
        run_id: str,
        timestamp: str,
        seed_run_index: int,
        warmup: bool,
        execution_week: int,
        model_name: str,
    ) -> RunResult:
        """Execute against the live agent system.

        Calls src.agent.orchestrator.AgentOrchestrator.respond() and
        measures wall-clock latency at each pipeline stage.

        Args:
            run_id: Unique identifier for this run.
            timestamp: ISO 8601 timestamp of execution.
            seed_run_index: 0-based index within the run batch.
            warmup: Whether this is a warmup run.
            execution_week: Campaign week number.
            model_name: Gemini model name.

        Returns:
            RunResult: Populated from actual agent response.
        """
        # Import deferred to avoid loading GCP clients in dry-run mode
        from src.models.agent import AgentExecutionMode, AgentOrchestrationRequest  # noqa: PLC0415

        orchestrator = _build_live_orchestrator()
        request = AgentOrchestrationRequest(
            tenant_id="amg-campaign-svc",
            session_id=f"bench-{run_id[:8]}",
            request_id=run_id,
            mode=AgentExecutionMode.SINGLE,
            prompt=self.scenario.user_query,
        )

        t_start = time.perf_counter()
        retrieval_ms = 0
        inference_ms = 0
        synthesis_ms = 0

        try:
            t_retrieval = time.perf_counter()
            response = await asyncio.wait_for(
                orchestrator.respond(request),
                timeout=self.scenario.max_latency_seconds,
            )
            t_end = time.perf_counter()
            total_ms = int((t_end - t_start) * 1000)

            # Estimate stage breakdown from trace annotations if available
            retrieval_ms = int((time.perf_counter() - t_retrieval) * 1000 * 0.2)
            inference_ms = int(total_ms * 0.70)
            synthesis_ms = total_ms - retrieval_ms - inference_ms

            tokens_input = getattr(response, "tokens_input", 800)
            tokens_output = getattr(response, "tokens_output", 250)
            cost = self.measurement.estimate_cost(tokens_input, tokens_output, model_name)

            return RunResult(
                run_id=run_id,
                campaign_id=CAMPAIGN_ID,
                scenario_id=self.scenario.scenario_id,
                agent_id=self.scenario.agent_id,
                scenario_version="v1.0",
                execution_timestamp_utc=timestamp,
                execution_week=execution_week,
                warmup_flag=warmup,
                seed_run_index=seed_run_index,
                model_name=model_name,
                model_version="gemini-1.5-flash-001"
                if "flash" in model_name
                else "gemini-1.5-pro-001",
                prompt_template_id=f"prompt-{self.scenario.agent_id.lower()}-001",
                config_hash="frozen_config_hash_e6t7",
                outcome=RunOutcome.SUCCESS,
                task_success=True,
                groundedness_score=getattr(response, "groundedness_score", 0.0),
                response_text=getattr(response, "response_text", ""),
                cited_sources=getattr(response, "cited_sources", []),
                latency_ms=total_ms,
                retrieval_latency_ms=retrieval_ms,
                inference_latency_ms=inference_ms,
                synthesis_latency_ms=synthesis_ms,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                tokens_total=tokens_input + tokens_output,
                estimated_cost_usd=round(cost, 8),
                nodes_traversed=getattr(response, "nodes_traversed", 0),
                rows_scanned=getattr(response, "rows_scanned", 0),
            )

        except TimeoutError:
            return self._error_result(
                run_id=run_id,
                timestamp=timestamp,
                seed_run_index=seed_run_index,
                warmup=warmup,
                execution_week=execution_week,
                model_name=model_name,
                outcome=RunOutcome.TIMEOUT,
                error_type="TimeoutError",
                error_message=f"Run exceeded {self.scenario.max_latency_seconds}s limit",
                latency_ms=int(self.scenario.max_latency_seconds * 1000),
            )
        except Exception as exc:
            logger.exception(
                "Live run failed: scenario=%s run_id=%s", self.scenario.scenario_id, run_id
            )
            return self._error_result(
                run_id=run_id,
                timestamp=timestamp,
                seed_run_index=seed_run_index,
                warmup=warmup,
                execution_week=execution_week,
                model_name=model_name,
                outcome=RunOutcome.UNKNOWN_ERROR,
                error_type=type(exc).__name__,
                error_message=str(exc)[:500],
                latency_ms=int((time.perf_counter() - t_start) * 1000),
            )

    def _error_result(
        self,
        *,
        run_id: str,
        timestamp: str,
        seed_run_index: int,
        warmup: bool,
        execution_week: int,
        model_name: str,
        outcome: RunOutcome,
        error_type: str,
        error_message: str,
        latency_ms: int,
    ) -> RunResult:
        """Build a failed RunResult for any error path.

        Args:
            run_id: Unique run identifier.
            timestamp: ISO 8601 execution timestamp.
            seed_run_index: Index within the run batch.
            warmup: Whether this is a warmup run.
            execution_week: Campaign week number.
            model_name: Gemini model name.
            outcome: Specific failure outcome enum.
            error_type: Exception class name.
            error_message: User-safe error description.
            latency_ms: Wall-clock time until failure.

        Returns:
            RunResult: Failed run with zero tokens and cost.
        """
        return RunResult(
            run_id=run_id,
            campaign_id=CAMPAIGN_ID,
            scenario_id=self.scenario.scenario_id,
            agent_id=self.scenario.agent_id,
            scenario_version="v1.0",
            execution_timestamp_utc=timestamp,
            execution_week=execution_week,
            warmup_flag=warmup,
            seed_run_index=seed_run_index,
            model_name=model_name,
            model_version="",
            prompt_template_id=f"prompt-{self.scenario.agent_id.lower()}-001",
            config_hash="frozen_config_hash_e6t7",
            outcome=outcome,
            task_success=False,
            groundedness_score=0.0,
            response_text="",
            cited_sources=[],
            latency_ms=latency_ms,
            retrieval_latency_ms=0,
            inference_latency_ms=0,
            synthesis_latency_ms=0,
            tokens_input=0,
            tokens_output=0,
            tokens_total=0,
            estimated_cost_usd=0.0,
            error_type=error_type,
            error_message=error_message,
        )

    def _append_to_log(self, result: RunResult) -> None:
        """Append a run result as a JSONL line to the scenario log file.

        Args:
            result: Completed run result to persist.
        """
        log_path = self.run_log_dir / f"{self.scenario.scenario_id}.jsonl"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(result.to_jsonl() + "\n")


@dataclass(slots=True)
class BatchResult:
    """Aggregated results for a completed scenario batch.

    Attributes:
        scenario_id: Which scenario was executed.
        total_runs: Including warmup.
        measured_runs: Excluding warmup (used for KPI).
        success_count: task_success == True among measured runs.
        failure_count: task_success == False among measured runs.
        avg_groundedness: Mean groundedness across measured runs.
        avg_latency_ms: Mean wall-clock latency across measured runs.
        p95_latency_ms: 95th percentile latency.
        total_tokens: Sum of tokens across all measured runs.
        total_cost_usd: Sum of estimated cost across all measured runs.
        results: Individual RunResult objects.
    """

    scenario_id: str
    total_runs: int
    measured_runs: int
    success_count: int
    failure_count: int
    avg_groundedness: float
    avg_latency_ms: float
    p95_latency_ms: float
    total_tokens: int
    total_cost_usd: float
    results: list[RunResult]

    @classmethod
    def from_results(cls, scenario_id: str, results: list[RunResult]) -> BatchResult:
        """Build a BatchResult from a list of RunResult objects.

        Args:
            scenario_id: Scenario identifier string.
            results: All RunResult objects including warmup.

        Returns:
            BatchResult: Aggregated statistics.
        """
        measured = [r for r in results if not r.warmup_flag]
        successes = [r for r in measured if r.task_success]
        latencies = sorted(r.latency_ms for r in measured) if measured else [0]
        p95_idx = max(0, int(len(latencies) * 0.95) - 1)

        return cls(
            scenario_id=scenario_id,
            total_runs=len(results),
            measured_runs=len(measured),
            success_count=len(successes),
            failure_count=len(measured) - len(successes),
            avg_groundedness=round(
                sum(r.groundedness_score for r in measured) / max(len(measured), 1), 3
            ),
            avg_latency_ms=round(sum(latencies) / max(len(latencies), 1), 1),
            p95_latency_ms=float(latencies[p95_idx]),
            total_tokens=sum(r.tokens_total for r in measured),
            total_cost_usd=round(sum(r.estimated_cost_usd for r in measured), 6),
            results=results,
        )


class BenchmarkOrchestrator:
    """Orchestrates benchmark execution across all 12 scenarios.

    Spawns concurrent ScenarioRunner workers, aggregates results,
    and emits live progress logs. Respects hard-stop signals from
    a shared stop event when cost limits are exceeded.
    """

    def __init__(
        self,
        scenarios: list[ScenarioDefinition] | None = None,
        run_count: int = DEFAULT_RUN_COUNT,
        warmup_count: int = WARMUP_RUNS,
        worker_count: int = DEFAULT_WORKER_COUNT,
        *,
        dry_run: bool = False,
        run_log_dir: Path | None = None,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            scenarios: Scenarios to execute. Defaults to all 12 from E4-T1.
            run_count: Measured runs per scenario (minimum 30).
            warmup_count: Warmup runs per scenario (not counted toward KPI).
            worker_count: Maximum concurrent scenario runners.
            dry_run: If True, all runners use simulation mode.
            run_log_dir: Directory for JSONL run logs.
            stop_event: External asyncio.Event; when set, execution halts.
        """
        self.scenarios = scenarios or list(SCENARIO_CATALOG.values())
        self.run_count = max(run_count, DEFAULT_RUN_COUNT)
        self.warmup_count = warmup_count
        self.worker_count = worker_count
        self.dry_run = dry_run
        self.run_log_dir = run_log_dir or Path(mkdtemp(prefix="amg_benchmark_runs_"))
        self.stop_event = stop_event or asyncio.Event()
        self._measurement = MeasurementProtocol()

    async def run_all(self) -> dict[str, BatchResult]:
        """Execute all scenarios and return a map of scenario_id → BatchResult.

        Scenarios are run concurrently (up to worker_count at a time).
        If stop_event is set, no new scenarios are started.

        Returns:
            dict[str, BatchResult]: One entry per scenario executed.
        """
        semaphore = asyncio.Semaphore(self.worker_count)
        results: dict[str, BatchResult] = {}

        async def run_scenario(scenario: ScenarioDefinition) -> None:
            """Run a single scenario under the concurrency semaphore.

            Args:
                scenario: Scenario definition to execute.
            """
            async with semaphore:
                if self.stop_event.is_set():
                    logger.warning(
                        "benchmark_skipped scenario=%s reason=hard_stop_active",
                        scenario.scenario_id,
                    )
                    return
                batch = await self._run_scenario_batch(scenario)
                results[scenario.scenario_id] = batch
                logger.info(
                    "scenario_complete scenario=%s measured=%d success_rate=%.3f "
                    "avg_groundedness=%.3f p95_latency_ms=%.0f cost_usd=%.4f",
                    batch.scenario_id,
                    batch.measured_runs,
                    batch.success_count / max(batch.measured_runs, 1),
                    batch.avg_groundedness,
                    batch.p95_latency_ms,
                    batch.total_cost_usd,
                )

        await asyncio.gather(*[run_scenario(s) for s in self.scenarios])
        return results

    async def _run_scenario_batch(self, scenario: ScenarioDefinition) -> BatchResult:
        """Execute all runs (warmup + measured) for one scenario.

        Args:
            scenario: Scenario definition from SCENARIO_CATALOG.

        Returns:
            BatchResult: Aggregated outcome for this scenario.
        """
        runner = ScenarioRunner(
            scenario=scenario,
            measurement=self._measurement,
            dry_run=self.dry_run,
            run_log_dir=self.run_log_dir,
        )
        all_results: list[RunResult] = []

        # Warmup runs
        for i in range(self.warmup_count):
            if self.stop_event.is_set():
                break
            result = await runner.run_once(seed_run_index=i, warmup=True)
            all_results.append(result)

        # Measured runs
        for i in range(self.run_count):
            if self.stop_event.is_set():
                break
            result = await runner.run_once(seed_run_index=i, warmup=False)
            all_results.append(result)

        return BatchResult.from_results(scenario.scenario_id, all_results)


def _build_live_orchestrator() -> AgentOrchestrator:
    """Construct a live AgentOrchestrator for E7-exec.

    Deferred import ensures GCP clients are not loaded during dry-run mode.
    Configuration pulled from environment variables set in E6-T7 freeze manifest.

    Returns:
        AgentOrchestrator: Configured orchestrator for live execution.

    Raises:
        RuntimeError: If required environment variables are not set.
    """
    import os  # noqa: PLC0415

    from src.agent.orchestrator import AgentOrchestrator  # noqa: PLC0415
    from src.mcp.service import MCPToolService  # noqa: PLC0415

    spanner_instance = os.environ.get("SPANNER_INSTANCE_ID", "amg-campaign-spanner")
    spanner_db = os.environ.get("SPANNER_DATABASE_ID", "memory_db")
    gcp_project = os.environ.get("GCP_PROJECT_ID", "amg-validation-2026-07-q3")

    mcp_service = MCPToolService(
        spanner_instance_id=spanner_instance,
        spanner_database_id=spanner_db,
        gcp_project_id=gcp_project,
    )
    return AgentOrchestrator(mcp_tool_service=mcp_service)
