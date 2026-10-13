"""Statistical analysis engine for E7 benchmark results.

Implements KPI scoring, confidence intervals, and effect size analysis
using formulas from E4-T5 (KPI SQL templates) and standard statistics.
No GCP access required — all computation is offline from RunResult objects.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import ClassVar, NamedTuple

# Per-scenario diagnostic thresholds from E4-T5 (used for run-level monitoring)
SUCCESS_RATE_THRESHOLD_DIAGNOSTIC = 0.75
SUCCESS_RATE_THRESHOLD_GOAL = 0.95
GROUNDEDNESS_THRESHOLD_DIAGNOSTIC = 0.75
GROUNDEDNESS_THRESHOLD_GOAL = 0.95

# Campaign-level acceptance thresholds from Plan §13 (go/no-go gate)
# These are the thresholds used by KPIScore.passes_* and overall_pass.
SUCCESS_RATE_THRESHOLD_ACCEPTABLE = 0.85  # §13: task success rate >= 85%
SUCCESS_RATE_CI_LOWER_THRESHOLD = 0.80  # §13: 95% CI lower bound >= 80%
GROUNDEDNESS_THRESHOLD_ACCEPTABLE = 0.90  # §13: groundedness >= 0.90
GROUNDEDNESS_CI_LOWER_THRESHOLD = 0.85  # §13: 95% CI lower bound >= 0.85
LATENCY_P95_THRESHOLD_MS = 10_000  # 10 seconds; per E4-T1 max latency specs
COST_PER_RUN_THRESHOLD_USD = 0.05
RELIABILITY_THRESHOLD = 0.95  # error rate < 5%

# Minimum sample size for 80% power, alpha=0.05, medium effect (d=0.5)
MIN_SAMPLE_SIZE = 30


class KPIScore(NamedTuple):
    """KPI scores for a scenario or campaign-level roll-up.

    Attributes:
        success_rate: Fraction of runs where task_success == True.
        avg_groundedness: Mean groundedness_score across measured runs.
        p95_latency_ms: 95th-percentile wall-clock latency.
        cost_per_run_usd: Mean estimated cost per measured run.
        reliability: 1 - (error_count / total_runs); excludes warmup.
        passes_success_rate: True if success_rate ≥ acceptable threshold.
        passes_groundedness: True if avg_groundedness ≥ acceptable threshold.
        passes_latency: True if p95_latency_ms ≤ threshold.
        passes_cost: True if cost_per_run_usd ≤ threshold.
        passes_reliability: True if reliability ≥ threshold.
    """

    success_rate: float
    avg_groundedness: float
    p95_latency_ms: float
    cost_per_run_usd: float
    reliability: float
    passes_success_rate: bool
    passes_groundedness: bool
    passes_latency: bool
    passes_cost: bool
    passes_reliability: bool

    @property
    def overall_pass(self) -> bool:
        """Return True only if all five KPIs pass campaign §13 thresholds.

        Success rate >= 85%, groundedness >= 0.90, latency p95 <= 10s,
        cost per run <= $0.05, reliability >= 95%.

        Returns:
            bool: True when all acceptance criteria are met.
        """
        return (
            self.passes_success_rate
            and self.passes_groundedness
            and self.passes_latency
            and self.passes_cost
            and self.passes_reliability
        )


@dataclass(frozen=True)
class ConfidenceInterval:
    """95% confidence interval for a single metric.

    Attributes:
        point_estimate: Sample mean.
        lower: Lower bound of the 95% CI.
        upper: Upper bound of the 95% CI.
        margin_of_error: Half-width of the interval (upper - point_estimate).
        n: Sample size.
        std_dev: Sample standard deviation.
    """

    point_estimate: float
    lower: float
    upper: float
    margin_of_error: float
    n: int
    std_dev: float

    @property
    def width(self) -> float:
        """Return full width of the confidence interval.

        Returns:
            float: upper - lower.
        """
        return self.upper - self.lower

    def contains(self, value: float) -> bool:
        """Return True if value falls within the CI bounds.

        Args:
            value: Value to test.

        Returns:
            bool: True if lower <= value <= upper.
        """
        return self.lower <= value <= self.upper


@dataclass(frozen=True)
class ComparisonResult:
    """Statistical comparison between two groups (e.g., scenario vs. baseline).

    Attributes:
        group_a_label: Label for the first group.
        group_b_label: Label for the second group.
        group_a_mean: Mean of group A.
        group_b_mean: Mean of group B.
        mean_difference: group_a_mean - group_b_mean.
        cohens_d: Standardized effect size (positive = A > B).
        p_value: Two-sample t-test p-value (approximate, Welch's t-test).
        is_significant: True if p_value < 0.05.
        n_a: Sample size of group A.
        n_b: Sample size of group B.
    """

    group_a_label: str
    group_b_label: str
    group_a_mean: float
    group_b_mean: float
    mean_difference: float
    cohens_d: float
    p_value: float
    is_significant: bool
    n_a: int
    n_b: int

    @property
    def effect_magnitude(self) -> str:
        """Classify effect size as negligible/small/medium/large.

        Cohen's d interpretation:
        - |d| < 0.2: negligible
        - 0.2 ≤ |d| < 0.5: small
        - 0.5 ≤ |d| < 0.8: medium
        - |d| ≥ 0.8: large

        Returns:
            str: One of 'negligible', 'small', 'medium', 'large'.
        """
        d = abs(self.cohens_d)
        if d < 0.2:  # noqa: PLR2004
            return "negligible"
        if d < 0.5:  # noqa: PLR2004
            return "small"
        if d < 0.8:  # noqa: PLR2004
            return "medium"
        return "large"


class KPIScoringEngine:
    """Compute KPI scores from benchmark RunResult objects.

    All methods accept lists of dicts (from RunResult.to_dict()) or
    typed RunResult instances for flexibility during E7-exec ingestion.
    """

    def score(self, run_dicts: list[dict]) -> KPIScore:
        """Compute all five KPIs from a list of run result dicts.

        Only measured runs (warmup_flag == False) are included.

        Args:
            run_dicts: List of dicts from RunResult.to_dict() or BigQuery rows.

        Returns:
            KPIScore: Five KPI scores with pass/fail evaluation.
        """
        measured = [r for r in run_dicts if not r.get("warmup_flag", False)]
        if not measured:
            return KPIScore(
                success_rate=0.0,
                avg_groundedness=0.0,
                p95_latency_ms=0.0,
                cost_per_run_usd=0.0,
                reliability=0.0,
                passes_success_rate=False,
                passes_groundedness=False,
                passes_latency=False,
                passes_cost=False,
                passes_reliability=False,
            )

        success_rate = self._success_rate(measured)
        avg_groundedness = self._avg_groundedness(measured)
        p95_latency = self._p95_latency(measured)
        cost_per_run = self._cost_per_run(measured)
        reliability = self._reliability(measured)

        # passes_* use campaign §13 thresholds, not E4-T5 diagnostic thresholds.
        return KPIScore(
            success_rate=round(success_rate, 4),
            avg_groundedness=round(avg_groundedness, 4),
            p95_latency_ms=round(p95_latency, 1),
            cost_per_run_usd=round(cost_per_run, 8),
            reliability=round(reliability, 4),
            passes_success_rate=success_rate >= SUCCESS_RATE_THRESHOLD_ACCEPTABLE,
            passes_groundedness=avg_groundedness >= GROUNDEDNESS_THRESHOLD_ACCEPTABLE,
            passes_latency=p95_latency <= LATENCY_P95_THRESHOLD_MS,
            passes_cost=cost_per_run <= COST_PER_RUN_THRESHOLD_USD,
            passes_reliability=reliability >= RELIABILITY_THRESHOLD,
        )

    def score_by_scenario(self, run_dicts: list[dict]) -> dict[str, KPIScore]:
        """Group run dicts by scenario_id and score each group.

        Args:
            run_dicts: All run result dicts (mixed scenarios).

        Returns:
            dict[str, KPIScore]: scenario_id → KPIScore for each scenario present.
        """
        by_scenario: dict[str, list[dict]] = {}
        for r in run_dicts:
            sid = r.get("scenario_id", "unknown")
            by_scenario.setdefault(sid, []).append(r)
        return {sid: self.score(runs) for sid, runs in by_scenario.items()}

    def _success_rate(self, measured: list[dict]) -> float:
        """Fraction of measured runs where task_success is True.

        Args:
            measured: Measured (non-warmup) run result dicts.

        Returns:
            float: Success rate in [0.0, 1.0].
        """
        return sum(1 for r in measured if r.get("task_success")) / len(measured)

    def _avg_groundedness(self, measured: list[dict]) -> float:
        """Mean groundedness_score across measured runs.

        Args:
            measured: Measured run result dicts.

        Returns:
            float: Mean groundedness in [0.0, 1.0].
        """
        return statistics.mean(r.get("groundedness_score", 0.0) for r in measured)

    def _p95_latency(self, measured: list[dict]) -> float:
        """95th-percentile latency_ms across measured runs.

        Args:
            measured: Measured run result dicts.

        Returns:
            float: p95 latency in milliseconds.
        """
        latencies = sorted(r.get("latency_ms", 0) for r in measured)
        idx = max(0, int(len(latencies) * 0.95) - 1)
        return float(latencies[idx])

    def _cost_per_run(self, measured: list[dict]) -> float:
        """Mean estimated cost per measured run.

        Args:
            measured: Measured run result dicts.

        Returns:
            float: Mean cost in USD.
        """
        costs = [r.get("estimated_cost_usd", 0.0) for r in measured]
        return statistics.mean(costs) if costs else 0.0

    def _reliability(self, measured: list[dict]) -> float:
        """1 - (error_count / total_measured), where errors are non-task outcomes.

        Errors are runs with outcome != 'success' AND outcome != 'task_failure'.
        task_failure is a valid benchmark outcome; system errors are not.

        Args:
            measured: Measured run result dicts.

        Returns:
            float: Reliability in [0.0, 1.0].
        """
        system_errors = sum(
            1 for r in measured if r.get("outcome") not in {"success", "task_failure"}
        )
        return 1.0 - (system_errors / len(measured))


class ConfidenceIntervalComputer:
    """Compute 95% confidence intervals using the t-distribution approximation.

    Uses the standard formula: CI = x̄ ± t*(s/√n)
    For n ≥ 30 (our minimum run count), t* ≈ 1.96 (normal approximation).
    For smaller samples, uses tabulated t-values.
    """

    # t* critical values for 95% CI (two-tailed), indexed by degrees of freedom
    _T_CRITICAL: ClassVar[dict[int, float]] = {
        1: 12.706,
        2: 4.303,
        3: 3.182,
        4: 2.776,
        5: 2.571,
        6: 2.447,
        7: 2.365,
        8: 2.306,
        9: 2.262,
        10: 2.228,
        15: 2.131,
        20: 2.086,
        25: 2.060,
        29: 2.045,
    }
    _T_LARGE_SAMPLE = 1.96  # n ≥ 30

    def compute(self, values: list[float]) -> ConfidenceInterval:
        """Compute the 95% CI for a list of numeric values.

        Args:
            values: Sample values (e.g., latency_ms or groundedness_score per run).

        Returns:
            ConfidenceInterval: Point estimate and CI bounds.

        Raises:
            ValueError: If values is empty.
        """
        if not values:
            msg = "Cannot compute confidence interval from empty sample"
            raise ValueError(msg)

        n = len(values)
        mean = statistics.mean(values)

        if n == 1:
            return ConfidenceInterval(
                point_estimate=round(mean, 6),
                lower=round(mean, 6),
                upper=round(mean, 6),
                margin_of_error=0.0,
                n=n,
                std_dev=0.0,
            )

        std_dev = statistics.stdev(values)
        se = std_dev / math.sqrt(n)
        t_star = self._t_critical(n - 1)
        margin = t_star * se

        return ConfidenceInterval(
            point_estimate=round(mean, 6),
            lower=round(mean - margin, 6),
            upper=round(mean + margin, 6),
            margin_of_error=round(margin, 6),
            n=n,
            std_dev=round(std_dev, 6),
        )

    def _t_critical(self, df: int) -> float:
        """Return the t* critical value for 95% CI.

        Args:
            df: Degrees of freedom (n - 1).

        Returns:
            float: t* critical value.
        """
        if df >= 29:  # noqa: PLR2004
            return self._T_LARGE_SAMPLE
        for threshold in sorted(self._T_CRITICAL.keys(), reverse=True):
            if df >= threshold:
                return self._T_CRITICAL[threshold]
        return self._T_CRITICAL[1]

    def compute_success_rate_ci(self, successes: int, n: int) -> ConfidenceInterval:
        """Wilson score confidence interval for a proportion.

        More accurate than normal approximation for proportions near 0 or 1.
        Formula: Wilson score interval with continuity correction.

        Args:
            successes: Number of successes.
            n: Total number of trials.

        Returns:
            ConfidenceInterval: CI for the success rate proportion.

        Raises:
            ValueError: If n is zero.
        """
        if n == 0:
            msg = "Sample size n must be greater than zero"
            raise ValueError(msg)

        p_hat = successes / n
        z = 1.96  # 95% CI
        z2 = z * z
        denominator = 1 + z2 / n
        center = (p_hat + z2 / (2 * n)) / denominator
        margin = (z / denominator) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))

        return ConfidenceInterval(
            point_estimate=round(p_hat, 6),
            lower=round(max(0.0, center - margin), 6),
            upper=round(min(1.0, center + margin), 6),
            margin_of_error=round(margin, 6),
            n=n,
            std_dev=round(math.sqrt(p_hat * (1 - p_hat)), 6),
        )


class EffectSizeAnalyzer:
    """Compute effect sizes and statistical significance for A/B comparisons.

    Used to compare scenario results against the locked baseline (E7-exec-T5).
    """

    def cohens_d(self, group_a: list[float], group_b: list[float]) -> float:
        """Compute Cohen's d effect size between two independent groups.

        Formula: d = (mean_A - mean_B) / pooled_std_dev
        Positive d means group A > group B.

        Args:
            group_a: Sample values for group A.
            group_b: Sample values for group B.

        Returns:
            float: Cohen's d (can be negative; sign indicates direction).

        Raises:
            ValueError: If either group is empty.
        """
        if not group_a or not group_b:
            msg = "Both groups must have at least one value"
            raise ValueError(msg)

        mean_a = statistics.mean(group_a)
        mean_b = statistics.mean(group_b)

        if len(group_a) == 1 and len(group_b) == 1:
            return mean_a - mean_b  # trivial case; no pooled std

        std_a = statistics.stdev(group_a) if len(group_a) > 1 else 0.0
        std_b = statistics.stdev(group_b) if len(group_b) > 1 else 0.0

        n_a = len(group_a)
        n_b = len(group_b)
        pooled_var = ((n_a - 1) * std_a**2 + (n_b - 1) * std_b**2) / (n_a + n_b - 2)
        pooled_std = math.sqrt(pooled_var) if pooled_var > 0 else 1.0

        return round((mean_a - mean_b) / pooled_std, 4)

    def welchs_t_test(self, group_a: list[float], group_b: list[float]) -> tuple[float, float]:
        """Compute Welch's t-test statistic and approximate p-value.

        Welch's test does not assume equal variances (more robust than Student's t).
        p-value is approximated using the normal distribution for n ≥ 30.

        Args:
            group_a: Sample values for group A.
            group_b: Sample values for group B.

        Returns:
            tuple[float, float]: (t_statistic, p_value).

        Raises:
            ValueError: If either group has fewer than 2 values.
        """
        if len(group_a) < 2 or len(group_b) < 2:  # noqa: PLR2004
            msg = "Each group must have at least 2 values for Welch's t-test"
            raise ValueError(msg)

        mean_a = statistics.mean(group_a)
        mean_b = statistics.mean(group_b)
        var_a = statistics.variance(group_a)
        var_b = statistics.variance(group_b)
        n_a = len(group_a)
        n_b = len(group_b)

        se = math.sqrt(var_a / n_a + var_b / n_b)
        if se == 0:
            return 0.0, 1.0

        t_stat = (mean_a - mean_b) / se
        # Approximate p-value using standard normal (valid for n ≥ 30)
        p_value = 2 * (1 - _normal_cdf(abs(t_stat)))
        return round(t_stat, 4), round(p_value, 6)

    def compare(
        self,
        group_a: list[float],
        group_b: list[float],
        label_a: str = "scenario",
        label_b: str = "baseline",
    ) -> ComparisonResult:
        """Full A/B comparison with effect size, t-test, and significance.

        Args:
            group_a: Sample values for group A (e.g., measured runs).
            group_b: Sample values for group B (e.g., baseline runs).
            label_a: Human-readable label for group A.
            label_b: Human-readable label for group B.

        Returns:
            ComparisonResult: Complete comparison statistics.
        """
        d = self.cohens_d(group_a, group_b)
        _t_stat, p_val = (
            self.welchs_t_test(group_a, group_b)
            if (
                len(group_a) >= 2 and len(group_b) >= 2  # noqa: PLR2004
            )
            else (0.0, 1.0)
        )

        return ComparisonResult(
            group_a_label=label_a,
            group_b_label=label_b,
            group_a_mean=round(statistics.mean(group_a), 6),
            group_b_mean=round(statistics.mean(group_b), 6),
            mean_difference=round(statistics.mean(group_a) - statistics.mean(group_b), 6),
            cohens_d=d,
            p_value=p_val,
            is_significant=p_val < 0.05,  # noqa: PLR2004
            n_a=len(group_a),
            n_b=len(group_b),
        )

    def min_sample_size(
        self,
        effect_size: float = 0.5,
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> int:
        """Compute minimum sample size for given effect size, alpha, and power.

        Approximation formula (Cohen, 1988) for two-sample t-test.
        For our campaign minimum (d=0.5, alpha=0.05, β=0.80) → n ≈ 64 per group.
        We use 30/scenario which is sufficient for d ≥ 0.7 (medium-large).

        Args:
            effect_size: Expected Cohen's d (default 0.5 = medium).
            alpha: Type I error rate (default 0.05).
            power: Statistical power 1 - β (default 0.80).

        Returns:
            int: Required samples per group.
        """
        z_alpha = _normal_ppf(1 - alpha / 2)
        z_beta = _normal_ppf(power)
        n = 2 * ((z_alpha + z_beta) / effect_size) ** 2
        return math.ceil(n)


def _normal_cdf(x: float) -> float:
    """Approximate the standard normal CDF using the error function.

    Args:
        x: Standard normal quantile.

    Returns:
        float: P(Z ≤ x) for Z ~ N(0,1).
    """
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def _normal_ppf(p: float) -> float:
    """Approximate the standard normal percent point function (inverse CDF).

    Uses a rational approximation (Abramowitz & Stegun 26.2.17).

    Args:
        p: Probability in (0, 1).

    Returns:
        float: x such that P(Z ≤ x) ≈ p.
    """
    if p <= 0 or p >= 1:
        msg = f"p must be in (0, 1), got {p}"
        raise ValueError(msg)

    sign = 1 if p >= 0.5 else -1  # noqa: PLR2004
    p_adj = p if p >= 0.5 else 1 - p  # noqa: PLR2004

    t = math.sqrt(-2.0 * math.log(1 - p_adj))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    numerator = c0 + c1 * t + c2 * t * t
    denominator = 1 + d1 * t + d2 * t * t + d3 * t * t * t
    return sign * (t - numerator / denominator)
