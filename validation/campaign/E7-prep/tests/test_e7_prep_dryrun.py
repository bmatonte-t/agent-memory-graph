"""Dry-run tests for E7-prep components.

Validates benchmark runners, statistics engine, and cost controller
without any GCP infrastructure access. All tests pass in offline mode.
Run with: python -m pytest E7-prep/tests/ -v
"""

from __future__ import annotations

import asyncio
import math
import sys
from pathlib import Path

import pytest

# Add E7-prep to path so imports resolve without installation
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark_runners import (
    SCENARIO_CATALOG,
    BatchResult,
    BenchmarkOrchestrator,
    MeasurementProtocol,
    RunOutcome,
    ScenarioDefinition,
    ScenarioRunner,
)
from cost_controller import (
    COST_HARD_STOP_USD,
    COST_SOFT_STOP_WARN_1_USD,
    COST_SOFT_STOP_WARN_2_USD,
    CostAttributionEngine,
    CostLedger,
    HardStopDecision,
    HardStopPolicy,
)
from statistics_engine import (
    GROUNDEDNESS_THRESHOLD_ACCEPTABLE,
    SUCCESS_RATE_THRESHOLD_ACCEPTABLE,
    ConfidenceIntervalComputer,
    EffectSizeAnalyzer,
    KPIScoringEngine,
)

# ─── ScenarioRunner ──────────────────────────────────────────────────────────


class TestScenarioRunner:
    """Dry-run tests for ScenarioRunner."""

    def test_catalog_has_12_scenarios(self) -> None:
        """All 12 EMC scenarios must be defined."""
        assert len(SCENARIO_CATALOG) == 12  # noqa: PLR2004

    def test_catalog_keys_match_scenario_ids(self) -> None:
        """Each key in the catalog must match its scenario_id field."""
        for key, scenario in SCENARIO_CATALOG.items():
            assert key == scenario.scenario_id

    def test_all_scenario_ids_format(self) -> None:
        """All scenario IDs must follow EMC-NNN format."""
        import re

        pattern = re.compile(r"^EMC-\d{3}$")
        for sid in SCENARIO_CATALOG:
            assert pattern.match(sid), f"Invalid scenario ID: {sid}"

    def test_dry_run_returns_run_result(self, tmp_path: Path) -> None:
        """Dry-run ScenarioRunner.run_once() must return a valid RunResult."""
        scenario = SCENARIO_CATALOG["EMC-001"]
        runner = ScenarioRunner(scenario=scenario, dry_run=True, run_log_dir=tmp_path)
        result = asyncio.run(runner.run_once(seed_run_index=0, warmup=False))

        assert result.scenario_id == "EMC-001"
        assert result.campaign_id == "amg-campaign-2026-06-29"
        assert result.run_id != ""
        assert result.latency_ms > 0
        assert 0.0 <= result.groundedness_score <= 1.0
        assert result.tokens_total > 0
        assert result.estimated_cost_usd >= 0.0

    def test_dry_run_writes_jsonl_log(self, tmp_path: Path) -> None:
        """Dry-run must write a JSONL line to the scenario log file."""
        scenario = SCENARIO_CATALOG["EMC-002"]
        runner = ScenarioRunner(scenario=scenario, dry_run=True, run_log_dir=tmp_path)
        asyncio.run(runner.run_once(seed_run_index=0))

        log_file = tmp_path / "EMC-002.jsonl"
        assert log_file.exists()
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1

        import json

        record = json.loads(lines[0])
        assert record["scenario_id"] == "EMC-002"
        assert "run_id" in record
        assert "groundedness_score" in record

    def test_warmup_flag_preserved(self, tmp_path: Path) -> None:
        """warmup_flag in RunResult must match the input argument."""
        scenario = SCENARIO_CATALOG["EMC-001"]
        runner = ScenarioRunner(scenario=scenario, dry_run=True, run_log_dir=tmp_path)

        warmup_result = asyncio.run(runner.run_once(seed_run_index=0, warmup=True))
        measured_result = asyncio.run(runner.run_once(seed_run_index=0, warmup=False))

        assert warmup_result.warmup_flag is True
        assert measured_result.warmup_flag is False

    def test_run_id_is_unique(self, tmp_path: Path) -> None:
        """Each run must produce a unique run_id."""
        scenario = SCENARIO_CATALOG["EMC-003"]
        runner = ScenarioRunner(scenario=scenario, dry_run=True, run_log_dir=tmp_path)

        results = [asyncio.run(runner.run_once(seed_run_index=i)) for i in range(10)]
        run_ids = [r.run_id for r in results]
        assert len(set(run_ids)) == 10  # noqa: PLR2004

    def test_batch_result_from_results(self, tmp_path: Path) -> None:
        """BatchResult.from_results() must compute correct aggregate stats."""
        scenario = SCENARIO_CATALOG["EMC-001"]
        runner = ScenarioRunner(scenario=scenario, dry_run=True, run_log_dir=tmp_path)
        results = [asyncio.run(runner.run_once(seed_run_index=i)) for i in range(10)]

        batch = BatchResult.from_results("EMC-001", results)
        assert batch.total_runs == 10  # noqa: PLR2004
        assert batch.measured_runs == 10  # noqa: PLR2004
        assert batch.success_count + batch.failure_count == 10  # noqa: PLR2004
        assert 0.0 <= batch.avg_groundedness <= 1.0
        assert batch.p95_latency_ms > 0
        assert batch.total_cost_usd >= 0.0


class TestBenchmarkOrchestrator:
    """Dry-run tests for BenchmarkOrchestrator."""

    def test_orchestrator_runs_all_scenarios(self, tmp_path: Path) -> None:
        """run_all() must return one BatchResult per scenario."""
        orchestrator = BenchmarkOrchestrator(
            run_count=5,
            warmup_count=1,
            worker_count=2,
            dry_run=True,
            run_log_dir=tmp_path,
        )
        results = asyncio.run(orchestrator.run_all())
        assert len(results) == 12  # noqa: PLR2004

    def test_orchestrator_respects_stop_event(self, tmp_path: Path) -> None:
        """When stop_event is set, orchestrator skips remaining scenarios."""
        stop_event = asyncio.Event()
        stop_event.set()  # pre-set: all scenarios should be skipped

        orchestrator = BenchmarkOrchestrator(
            run_count=5,
            dry_run=True,
            run_log_dir=tmp_path,
            stop_event=stop_event,
        )
        results = asyncio.run(orchestrator.run_all())
        assert len(results) == 0

    def test_orchestrator_minimum_run_count(self, tmp_path: Path) -> None:
        """run_count below 30 must be raised to 30 (E4-T1 minimum)."""
        orchestrator = BenchmarkOrchestrator(run_count=5, dry_run=True, run_log_dir=tmp_path)
        assert orchestrator.run_count == 30  # noqa: PLR2004


# ─── MeasurementProtocol ─────────────────────────────────────────────────────


class TestMeasurementProtocol:
    """Tests for cost estimation."""

    def test_flash_cost_estimate(self) -> None:
        """Flash model cost calculation matches E4-T6 pricing."""
        m = MeasurementProtocol()
        cost = m.estimate_cost(tokens_input=1000, tokens_output=300, model_name="gemini-1.5-flash")
        expected = (1000 / 1_000_000 * 0.075) + (300 / 1_000_000 * 0.30)
        assert math.isclose(cost, expected, rel_tol=1e-9)

    def test_pro_cost_estimate(self) -> None:
        """Pro model cost calculation matches E4-T6 pricing."""
        m = MeasurementProtocol()
        cost = m.estimate_cost(tokens_input=1000, tokens_output=300, model_name="gemini-1.5-pro")
        expected = (1000 / 1_000_000 * 1.50) + (300 / 1_000_000 * 6.00)
        assert math.isclose(cost, expected, rel_tol=1e-9)

    def test_ta_agent_uses_pro_model(self) -> None:
        """AGENT-TA must be assigned the Pro model per E2-T2."""
        m = MeasurementProtocol()
        assert m.model_for_agent("AGENT-TA") == "gemini-1.5-pro"

    def test_ec_agent_uses_flash_model(self) -> None:
        """AGENT-EC must be assigned the Flash model per E2-T2."""
        m = MeasurementProtocol()
        assert m.model_for_agent("AGENT-EC") == "gemini-1.5-flash"


# ─── KPIScoringEngine ────────────────────────────────────────────────────────


class TestKPIScoringEngine:
    """Tests for KPI computation from run result dicts."""

    def _mock_runs(
        self,
        n: int = 30,
        success_rate: float = 0.87,
        groundedness: float = 0.82,
        latency_ms: int = 3000,
        cost_usd: float = 0.001,
    ) -> list[dict]:
        """Generate synthetic run result dicts for testing."""
        import random

        rng = random.Random(42)
        runs = []
        for i in range(n):
            task_success = rng.random() < success_rate
            runs.append(
                {
                    "run_id": f"test-{i}",
                    "warmup_flag": False,
                    "task_success": task_success,
                    "groundedness_score": groundedness if task_success else 0.2,
                    "latency_ms": latency_ms + rng.randint(-500, 500),
                    "estimated_cost_usd": cost_usd,
                    "outcome": "success" if task_success else "task_failure",
                }
            )
        return runs

    def test_success_rate_computed(self) -> None:
        """success_rate must be close to the mocked rate."""
        runs = self._mock_runs(n=100, success_rate=0.87)
        engine = KPIScoringEngine()
        score = engine.score(runs)
        assert 0.80 <= score.success_rate <= 0.94

    def test_passes_success_rate_threshold(self) -> None:
        """Success rate above 0.85 (plan §13 threshold) must pass."""
        runs = self._mock_runs(n=30, success_rate=0.90)
        score = KPIScoringEngine().score(runs)
        assert score.passes_success_rate is True

    def test_fails_success_rate_below_campaign_threshold(self) -> None:
        """Success rate below 0.85 (plan §13 threshold) must fail."""
        runs = self._mock_runs(n=30, success_rate=0.50)
        score = KPIScoringEngine().score(runs)
        assert score.passes_success_rate is False

    def test_fails_success_rate_below_85_pct(self) -> None:
        """Success rate of 0.80 must fail the 0.85 campaign gate."""
        runs = self._mock_runs(n=100, success_rate=0.80)
        score = KPIScoringEngine().score(runs)
        assert score.passes_success_rate is False

    def test_passes_groundedness_campaign_threshold(self) -> None:
        """Groundedness above 0.90 (plan §13) must pass."""
        runs = self._mock_runs(n=30, success_rate=1.0, groundedness=0.93)
        score = KPIScoringEngine().score(runs)
        assert score.passes_groundedness is True

    def test_fails_groundedness_below_campaign_threshold(self) -> None:
        """Groundedness below 0.90 (plan §13) must fail, even if 'diagnostically acceptable'."""
        runs = self._mock_runs(n=30, success_rate=1.0, groundedness=0.80)
        score = KPIScoringEngine().score(runs)
        assert score.passes_groundedness is False

    def test_groundedness_computed(self) -> None:
        """avg_groundedness must be non-zero for successful runs."""
        runs = self._mock_runs(n=30, success_rate=1.0, groundedness=0.85)
        score = KPIScoringEngine().score(runs)
        assert score.avg_groundedness > 0.70  # noqa: PLR2004

    def test_warmup_runs_excluded(self) -> None:
        """Warmup runs (warmup_flag=True) must not affect KPI scores."""
        measured = self._mock_runs(n=30, success_rate=0.90)
        warmup = [dict(r, warmup_flag=True, task_success=False) for r in measured[:5]]
        all_runs = measured + warmup

        score = KPIScoringEngine().score(all_runs)
        assert score.success_rate > SUCCESS_RATE_THRESHOLD_ACCEPTABLE

    def test_empty_input_returns_zero_scores(self) -> None:
        """Empty input must return zero scores, all failing."""
        score = KPIScoringEngine().score([])
        assert score.overall_pass is False

    def test_score_by_scenario(self) -> None:
        """score_by_scenario() must return one KPIScore per scenario present."""
        runs_001 = [dict(r, scenario_id="EMC-001") for r in self._mock_runs(n=30)]
        runs_002 = [dict(r, scenario_id="EMC-002") for r in self._mock_runs(n=30)]

        scores = KPIScoringEngine().score_by_scenario(runs_001 + runs_002)
        assert set(scores.keys()) == {"EMC-001", "EMC-002"}


# ─── ConfidenceIntervalComputer ───────────────────────────────────────────────


class TestConfidenceIntervalComputer:
    """Tests for confidence interval computation."""

    def test_ci_contains_true_mean(self) -> None:
        """95% CI must contain the true mean for normally distributed data."""
        import random

        rng = random.Random(99)
        true_mean = 3500.0
        values = [true_mean + rng.gauss(0, 200) for _ in range(30)]
        ci = ConfidenceIntervalComputer().compute(values)
        assert ci.lower <= true_mean <= ci.upper

    def test_larger_sample_narrower_ci(self) -> None:
        """Larger sample should produce narrower confidence interval."""
        import random

        rng = random.Random(77)
        values_small = [rng.gauss(100, 20) for _ in range(10)]
        values_large = [rng.gauss(100, 20) for _ in range(100)]
        ci_small = ConfidenceIntervalComputer().compute(values_small)
        ci_large = ConfidenceIntervalComputer().compute(values_large)
        assert ci_large.width < ci_small.width

    def test_single_value_returns_point_ci(self) -> None:
        """Single-value input must return a CI with zero width."""
        ci = ConfidenceIntervalComputer().compute([42.0])
        assert ci.point_estimate == 42.0  # noqa: PLR2004
        assert ci.width == 0.0

    def test_empty_input_raises(self) -> None:
        """Empty input must raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            ConfidenceIntervalComputer().compute([])

    def test_success_rate_ci_within_bounds(self) -> None:
        """Success rate CI must stay within [0, 1]."""
        ci = ConfidenceIntervalComputer().compute_success_rate_ci(successes=26, n=30)
        assert 0.0 <= ci.lower <= 1.0
        assert 0.0 <= ci.upper <= 1.0
        assert ci.lower <= ci.upper

    def test_success_rate_ci_zero_n_raises(self) -> None:
        """n=0 must raise ValueError."""
        with pytest.raises(ValueError, match="greater than zero"):
            ConfidenceIntervalComputer().compute_success_rate_ci(successes=0, n=0)


# ─── EffectSizeAnalyzer ───────────────────────────────────────────────────────


class TestEffectSizeAnalyzer:
    """Tests for Cohen's d and statistical significance."""

    def test_cohens_d_identical_groups_is_zero(self) -> None:
        """Groups with the same values must produce d ≈ 0."""
        group = [0.85] * 30
        d = EffectSizeAnalyzer().cohens_d(group, group)
        assert abs(d) < 0.01  # noqa: PLR2004

    def test_cohens_d_direction(self) -> None:
        """d must be positive when group A > group B."""
        a = [0.90] * 30
        b = [0.70] * 30
        d = EffectSizeAnalyzer().cohens_d(a, b)
        assert d > 0

    def test_cohens_d_magnitude_medium(self) -> None:
        """A well-separated pair must produce medium effect size."""
        import random

        rng = random.Random(55)
        a = [rng.gauss(0.85, 0.05) for _ in range(30)]
        b = [rng.gauss(0.70, 0.05) for _ in range(30)]
        d = EffectSizeAnalyzer().cohens_d(a, b)
        assert d > 0.5  # noqa: PLR2004  medium effect

    def test_significant_difference_detected(self) -> None:
        """Clearly separated groups must yield p < 0.05."""
        import random

        rng = random.Random(33)
        a = [rng.gauss(0.90, 0.03) for _ in range(30)]
        b = [rng.gauss(0.70, 0.03) for _ in range(30)]
        result = EffectSizeAnalyzer().compare(a, b, "scenario", "baseline")
        assert result.is_significant is True
        assert result.mean_difference > 0

    def test_no_significance_for_identical_groups(self) -> None:
        """Identical groups must not yield statistical significance."""
        import random

        rng = random.Random(22)
        group = [rng.gauss(0.80, 0.05) for _ in range(30)]
        result = EffectSizeAnalyzer().compare(group, group)
        assert result.is_significant is False

    def test_effect_magnitude_labels(self) -> None:
        """Effect magnitude labels must follow Cohen's conventions."""
        analyzer = EffectSizeAnalyzer()
        a_neg = [0.0] * 30
        b_large = [1.0] * 30
        result = analyzer.compare(a_neg, b_large)
        assert result.effect_magnitude in {"large", "medium"}  # clearly separated

    def test_min_sample_size_medium_effect(self) -> None:
        """Minimum sample size for d=0.5 must be approximately 64."""
        n = EffectSizeAnalyzer().min_sample_size(effect_size=0.5)
        assert 55 <= n <= 75  # noqa: PLR2004


# ─── CostLedger ──────────────────────────────────────────────────────────────


class TestCostLedger:
    """Tests for cost tracking."""

    def test_total_spent_accumulates(self) -> None:
        """total_spent() must sum all recorded entries."""
        ledger = CostLedger()
        ledger.record("run-1", "EMC-001", "AGENT-EC", 800, 300, "gemini-1.5-flash", 0.000163)
        ledger.record("run-2", "EMC-002", "AGENT-EC", 900, 250, "gemini-1.5-flash", 0.000143)
        assert math.isclose(ledger.total_spent(), 0.000306, rel_tol=1e-6)

    def test_remaining_budget_decreases(self) -> None:
        """remaining_budget() must decrease as runs are recorded."""
        ledger = CostLedger()
        initial = ledger.remaining_budget()
        ledger.record("run-1", "EMC-001", "AGENT-EC", 800, 300, "gemini-1.5-flash", 1.50)
        assert ledger.remaining_budget() < initial

    def test_spent_by_scenario_grouping(self) -> None:
        """spent_by_scenario() must group costs correctly."""
        ledger = CostLedger()
        ledger.record("r1", "EMC-001", "AGENT-EC", 800, 300, "gemini-1.5-flash", 0.50)
        ledger.record("r2", "EMC-001", "AGENT-EC", 800, 300, "gemini-1.5-flash", 0.50)
        ledger.record("r3", "EMC-002", "AGENT-EC", 800, 300, "gemini-1.5-flash", 0.25)

        by_scenario = ledger.spent_by_scenario()
        assert math.isclose(by_scenario["EMC-001"], 1.00, rel_tol=1e-6)
        assert math.isclose(by_scenario["EMC-002"], 0.25, rel_tol=1e-6)

    def test_forecast_total(self) -> None:
        """forecast_total() must extrapolate correctly from current average."""
        ledger = CostLedger()
        for i in range(10):
            ledger.record(f"r{i}", "EMC-001", "AGENT-EC", 800, 300, "gemini-1.5-flash", 0.10)
        forecast = ledger.forecast_total(total_expected_runs=360)
        assert math.isclose(forecast, 36.0, rel_tol=1e-4)


# ─── HardStopPolicy ──────────────────────────────────────────────────────────


class TestHardStopPolicy:
    """Tests for hard-stop enforcement."""

    def test_proceed_below_warn_1(self) -> None:
        """Spending below $200 must return PROCEED."""
        assert HardStopPolicy().evaluate(150.0) == HardStopDecision.PROCEED

    def test_warn_1_at_threshold(self) -> None:
        """Spending at exactly $200 must return WARN_1."""
        assert HardStopPolicy().evaluate(COST_SOFT_STOP_WARN_1_USD) == HardStopDecision.WARN_1

    def test_warn_2_at_threshold(self) -> None:
        """Spending at exactly $240 must return WARN_2."""
        assert HardStopPolicy().evaluate(COST_SOFT_STOP_WARN_2_USD) == HardStopDecision.WARN_2

    def test_stop_at_hard_limit(self) -> None:
        """Spending at exactly $260 must return STOP."""
        assert HardStopPolicy().evaluate(COST_HARD_STOP_USD) == HardStopDecision.STOP

    def test_stop_above_hard_limit(self) -> None:
        """Spending above $260 must still return STOP."""
        assert HardStopPolicy().evaluate(300.0) == HardStopDecision.STOP

    def test_should_halt_only_on_stop(self) -> None:
        """should_halt() must return True only when STOP is triggered."""
        policy = HardStopPolicy()
        assert policy.should_halt(150.0) is False
        assert policy.should_halt(200.0) is False
        assert policy.should_halt(260.0) is True
        assert policy.should_halt(261.0) is True


# ─── CostAttributionEngine ───────────────────────────────────────────────────


class TestCostAttributionEngine:
    """Tests for token-to-cost conversion."""

    def test_flash_estimate_matches_e4t6(self) -> None:
        """Flash cost per 1,400 tokens must match E4-T6 calculation."""
        engine = CostAttributionEngine()
        cost = engine.estimate_cost(1100, 300, "gemini-1.5-flash")
        expected = (1100 / 1_000_000 * 0.075) + (300 / 1_000_000 * 0.30)
        assert math.isclose(cost, expected, rel_tol=1e-9)

    def test_pro_more_expensive_than_flash(self) -> None:
        """Pro model must always cost more than Flash for same tokens."""
        engine = CostAttributionEngine()
        flash_cost = engine.estimate_cost(1000, 300, "gemini-1.5-flash")
        pro_cost = engine.estimate_cost(1000, 300, "gemini-1.5-pro")
        assert pro_cost > flash_cost

    def test_agent_model_assignments(self) -> None:
        """Model assignments must match E2-T2 agent profiles."""
        engine = CostAttributionEngine()
        assert "flash" in engine.model_for_agent("AGENT-EC")
        assert "flash" in engine.model_for_agent("AGENT-CC")
        assert "flash" in engine.model_for_agent("AGENT-SI")
        assert "flash" in engine.model_for_agent("AGENT-CM")
        assert "pro" in engine.model_for_agent("AGENT-TA")
        assert "pro" in engine.model_for_agent("AGENT-CA")

    def test_campaign_cost_estimate_within_budget(self) -> None:
        """Estimated LLM cost for full campaign must be well under $260."""
        engine = CostAttributionEngine()
        estimate = engine.estimate_campaign_cost()
        assert estimate["llm_inference_total_usd"] < 10.0  # noqa: PLR2004  LLM only is ~$0.36
        assert estimate["grand_total_estimate_usd"] < 260.0  # noqa: PLR2004
