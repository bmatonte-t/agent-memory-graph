"""Cost tracking and hard-stop enforcement for E7 benchmark execution.

Implements CostLedger, HardStopPolicy, and CostAttributionEngine from
E4-T6 (cost control ledger design). Runs throughout E7-exec monitoring loop.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Budget constants from E4-T6 (immutable)
CAMPAIGN_BUDGET_HARD_LIMIT_USD = 300.0
COST_HARD_STOP_USD = 260.0
COST_SOFT_STOP_WARN_1_USD = 200.0
COST_SOFT_STOP_WARN_2_USD = 240.0
COST_BUFFER_USD = 40.0  # reserved for cleanup

# Gemini pricing from E4-T6
GEMINI_FLASH_INPUT_PER_M = 0.075
GEMINI_FLASH_OUTPUT_PER_M = 0.30
GEMINI_PRO_INPUT_PER_M = 1.50
GEMINI_PRO_OUTPUT_PER_M = 6.00


class HardStopDecision(str, Enum):
    """Decision returned by HardStopPolicy.evaluate().

    Attributes:
        PROCEED: Budget utilization is within safe range.
        WARN_1: First warning threshold reached ($200).
        WARN_2: Second warning threshold reached ($240).
        STOP: Hard stop triggered ($260). Execution must halt.
    """

    PROCEED = "proceed"
    WARN_1 = "warn_1"
    WARN_2 = "warn_2"
    STOP = "stop"


class CostEntry(NamedTuple):
    """A single cost record in the ledger.

    Attributes:
        run_id: UUID of the benchmark run.
        scenario_id: Which scenario (EMC-001 through EMC-012).
        agent_id: Agent that performed the run.
        tokens_input: Input tokens consumed.
        tokens_output: Output tokens generated.
        model_name: Gemini model name.
        estimated_cost_usd: Calculated cost for this run.
        timestamp: Unix timestamp when the run was recorded.
    """

    run_id: str
    scenario_id: str
    agent_id: str
    tokens_input: int
    tokens_output: int
    model_name: str
    estimated_cost_usd: float
    timestamp: float


@dataclass
class CostLedger:
    """Tracks cumulative spending by run and scenario during E7-exec.

    Thread-safe for single-process asyncio use; not safe for concurrent
    process writes (use BigQuery for multi-process tracking in production).
    """

    _entries: list[CostEntry] = field(default_factory=list)

    def record(
        self,
        run_id: str,
        scenario_id: str,
        agent_id: str,
        tokens_input: int,
        tokens_output: int,
        model_name: str,
        estimated_cost_usd: float,
    ) -> CostEntry:
        """Record a completed run's cost in the ledger.

        Args:
            run_id: Unique run identifier from RunResult.run_id.
            scenario_id: Scenario that was executed.
            agent_id: Agent that executed the scenario.
            tokens_input: Input tokens from RunResult.tokens_input.
            tokens_output: Output tokens from RunResult.tokens_output.
            model_name: Model used (gemini-1.5-flash or gemini-1.5-pro).
            estimated_cost_usd: Cost from MeasurementProtocol.estimate_cost().

        Returns:
            CostEntry: The recorded entry.
        """
        entry = CostEntry(
            run_id=run_id,
            scenario_id=scenario_id,
            agent_id=agent_id,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            model_name=model_name,
            estimated_cost_usd=estimated_cost_usd,
            timestamp=time.time(),
        )
        self._entries.append(entry)
        return entry

    def total_spent(self) -> float:
        """Return cumulative spend across all recorded runs.

        Returns:
            float: Total USD spent so far.
        """
        return round(sum(e.estimated_cost_usd for e in self._entries), 6)

    def remaining_budget(self) -> float:
        """Return remaining budget before hard-stop.

        Returns:
            float: COST_HARD_STOP_USD - total_spent(). May be negative if overspent.
        """
        return round(COST_HARD_STOP_USD - self.total_spent(), 6)

    def spent_by_scenario(self) -> dict[str, float]:
        """Return total spend grouped by scenario_id.

        Returns:
            dict[str, float]: scenario_id → total USD spent.
        """
        result: dict[str, float] = {}
        for entry in self._entries:
            result[entry.scenario_id] = round(
                result.get(entry.scenario_id, 0.0) + entry.estimated_cost_usd, 6
            )
        return result

    def spent_by_agent(self) -> dict[str, float]:
        """Return total spend grouped by agent_id.

        Returns:
            dict[str, float]: agent_id → total USD spent.
        """
        result: dict[str, float] = {}
        for entry in self._entries:
            result[entry.agent_id] = round(
                result.get(entry.agent_id, 0.0) + entry.estimated_cost_usd, 6
            )
        return result

    def run_count(self, include_warmup: bool = True) -> int:  # noqa: ARG002
        """Return total number of recorded runs.

        Args:
            include_warmup: Unused; warmup not separately tracked in ledger.

        Returns:
            int: Number of CostEntry records.
        """
        return len(self._entries)

    def avg_cost_per_run(self) -> float:
        """Return mean estimated cost per run across all recorded entries.

        Returns:
            float: Mean USD per run. Returns 0.0 if no runs recorded.
        """
        if not self._entries:
            return 0.0
        return round(self.total_spent() / len(self._entries), 8)

    def forecast_total(self, total_expected_runs: int) -> float:
        """Forecast total campaign cost based on current average cost per run.

        Args:
            total_expected_runs: Total runs expected in the campaign.

        Returns:
            float: Projected total USD cost.
        """
        if not self._entries:
            return 0.0
        return round(self.avg_cost_per_run() * total_expected_runs, 4)

    def summary(self) -> dict:
        """Return a dict summary for logging and reporting.

        Returns:
            dict: Key cost metrics for structured log output.
        """
        return {
            "total_spent_usd": self.total_spent(),
            "remaining_budget_usd": self.remaining_budget(),
            "run_count": self.run_count(),
            "avg_cost_per_run_usd": self.avg_cost_per_run(),
            "hard_stop_threshold_usd": COST_HARD_STOP_USD,
            "utilization_pct": round(self.total_spent() / COST_HARD_STOP_USD * 100, 1),
            "by_scenario": self.spent_by_scenario(),
            "by_agent": self.spent_by_agent(),
        }


class HardStopPolicy:
    """Enforce the $260 hard-stop limit with graduated warnings.

    Thresholds from E4-T6:
    - WARN_1 at $200 (77% utilization): inform PVL; continue execution.
    - WARN_2 at $240 (92% utilization): PVL signs off required to proceed.
    - STOP at $260 (100% of limit): execution halts immediately; no new runs started.
    """

    def evaluate(self, current_spent: float) -> HardStopDecision:
        """Evaluate the current spending against all thresholds.

        Args:
            current_spent: Current cumulative spend in USD.

        Returns:
            HardStopDecision: Action to take based on spend level.
        """
        if current_spent >= COST_HARD_STOP_USD:
            logger.critical(
                "cost_hard_stop_triggered spent_usd=%.4f limit_usd=%.2f",
                current_spent,
                COST_HARD_STOP_USD,
            )
            return HardStopDecision.STOP

        if current_spent >= COST_SOFT_STOP_WARN_2_USD:
            logger.warning(
                "cost_warn_2 spent_usd=%.4f threshold_usd=%.2f remaining_usd=%.4f",
                current_spent,
                COST_SOFT_STOP_WARN_2_USD,
                COST_HARD_STOP_USD - current_spent,
            )
            return HardStopDecision.WARN_2

        if current_spent >= COST_SOFT_STOP_WARN_1_USD:
            logger.warning(
                "cost_warn_1 spent_usd=%.4f threshold_usd=%.2f remaining_usd=%.4f",
                current_spent,
                COST_SOFT_STOP_WARN_1_USD,
                COST_HARD_STOP_USD - current_spent,
            )
            return HardStopDecision.WARN_1

        return HardStopDecision.PROCEED

    def should_halt(self, current_spent: float) -> bool:
        """Return True if execution must stop immediately.

        Args:
            current_spent: Current cumulative spend in USD.

        Returns:
            bool: True only when HardStopDecision.STOP is triggered.
        """
        return self.evaluate(current_spent) == HardStopDecision.STOP


class CostAttributionEngine:
    """Map token counts to cost estimates per Gemini model.

    Pricing from E4-T6; frozen for the campaign duration.
    Agents EC, CC, SI, CM use Flash; TA, CA use Pro (from E2-T2).
    """

    # Agent → model assignment from E2-T2
    _AGENT_MODEL_MAP: dict[str, str] = {
        "AGENT-EC": "gemini-1.5-flash",
        "AGENT-CC": "gemini-1.5-flash",
        "AGENT-SI": "gemini-1.5-flash",
        "AGENT-CM": "gemini-1.5-flash",
        "AGENT-TA": "gemini-1.5-pro",
        "AGENT-CA": "gemini-1.5-pro",
    }

    def estimate_cost(
        self,
        tokens_input: int,
        tokens_output: int,
        model_name: str,
    ) -> float:
        """Estimate cost from token counts and model name.

        Args:
            tokens_input: Number of input tokens.
            tokens_output: Number of output tokens.
            model_name: Gemini model name (must contain 'flash' or 'pro').

        Returns:
            float: Estimated USD cost (precision: 8 decimal places).
        """
        if "pro" in model_name.lower():
            cost = (
                tokens_input / 1_000_000 * GEMINI_PRO_INPUT_PER_M
                + tokens_output / 1_000_000 * GEMINI_PRO_OUTPUT_PER_M
            )
        else:
            cost = (
                tokens_input / 1_000_000 * GEMINI_FLASH_INPUT_PER_M
                + tokens_output / 1_000_000 * GEMINI_FLASH_OUTPUT_PER_M
            )
        return round(cost, 8)

    def model_for_agent(self, agent_id: str) -> str:
        """Look up the Gemini model assigned to an agent.

        Args:
            agent_id: Agent identifier (e.g., AGENT-EC).

        Returns:
            str: Model name; defaults to Flash for unknown agents.
        """
        return self._AGENT_MODEL_MAP.get(agent_id, "gemini-1.5-flash")

    def estimate_campaign_cost(
        self,
        runs_per_scenario: int = 30,
        n_scenarios: int = 12,
        avg_tokens_flash_input: int = 900,
        avg_tokens_flash_output: int = 300,
        avg_tokens_pro_input: int = 1100,
        avg_tokens_pro_output: int = 350,
        flash_scenarios: int = 9,
        pro_scenarios: int = 3,
    ) -> dict[str, float]:
        """Estimate total LLM inference cost for the full campaign.

        Based on E4-T6 cost model; 9 scenarios use Flash, 3 use Pro
        (EMC-001 through EMC-009 = Flash; EMC-010=SI/Flash, EMC-011=CM/Flash,
        EMC-012=CA/Pro; EMC-007/008/009=TA/Pro — actual: TA is 3 scenarios).

        Args:
            runs_per_scenario: Minimum measured runs per scenario.
            n_scenarios: Total number of scenarios.
            avg_tokens_flash_input: Average input tokens for Flash model runs.
            avg_tokens_flash_output: Average output tokens for Flash model runs.
            avg_tokens_pro_input: Average input tokens for Pro model runs.
            avg_tokens_pro_output: Average output tokens for Pro model runs.
            flash_scenarios: Number of scenarios using Flash model.
            pro_scenarios: Number of scenarios using Pro model.

        Returns:
            dict[str, float]: Breakdown of estimated costs by model and total.
        """
        flash_cost_per_run = self.estimate_cost(
            avg_tokens_flash_input, avg_tokens_flash_output, "gemini-1.5-flash"
        )
        pro_cost_per_run = self.estimate_cost(
            avg_tokens_pro_input, avg_tokens_pro_output, "gemini-1.5-pro"
        )

        total_flash = flash_cost_per_run * runs_per_scenario * flash_scenarios
        total_pro = pro_cost_per_run * runs_per_scenario * pro_scenarios

        return {
            "flash_cost_per_run_usd": flash_cost_per_run,
            "pro_cost_per_run_usd": pro_cost_per_run,
            "flash_total_usd": round(total_flash, 4),
            "pro_total_usd": round(total_pro, 4),
            "llm_inference_total_usd": round(total_flash + total_pro, 4),
            "overhead_estimate_usd": round(
                (total_flash + total_pro) * 10, 4
            ),  # ~10x overhead (BQ, Spanner, etc.)
            "grand_total_estimate_usd": round((total_flash + total_pro) * 11, 4),
        }
