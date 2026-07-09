#!/usr/bin/env bash
# E7-exec Benchmark Launch Script
# Spawns benchmark runners for all 12 EMC scenarios.
# Usage: ./scripts/launch_benchmarks.sh [--dry-run] [--scenario EMC-001]
# Must run AFTER deploy_observability.sh exits 0.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E7_PREP_DIR="${SCRIPT_DIR}/.."
LOG_DIR="/tmp/amg_benchmark_runs"
COST_LOG="${LOG_DIR}/cost_ledger.jsonl"
SUMMARY_FILE="${LOG_DIR}/execution_summary.json"

DRY_RUN=""
SCENARIO_FILTER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN="--dry-run"; shift ;;
        --scenario) SCENARIO_FILTER="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

GCP_PROJECT="${GCP_PROJECT_ID:-amg-validation-2026-07-q3}"
SPANNER_INSTANCE="${SPANNER_INSTANCE_ID:-amg-campaign-spanner}"
SPANNER_DB="${SPANNER_DATABASE_ID:-memory_db}"
WORKER_COUNT="${BENCHMARK_WORKERS:-4}"
RUN_COUNT="${BENCHMARK_RUNS_PER_SCENARIO:-30}"
EXECUTION_WEEK=3

# ─── Helpers ──────────────────────────────────────────────────────────────────

log_info() { echo "[INFO]  $(date -u +%H:%M:%SZ)  $*"; }
log_ok()   { echo "[OK]    $(date -u +%H:%M:%SZ)  $*"; }
log_warn() { echo "[WARN]  $(date -u +%H:%M:%SZ)  $*"; }
log_fail() { echo "[FAIL]  $(date -u +%H:%M:%SZ)  $*"; }

# ─── Preamble ─────────────────────────────────────────────────────────────────

mkdir -p "${LOG_DIR}"
log_info "AMG Benchmark Launch Script"
log_info "Campaign:          amg-campaign-2026-06-29"
log_info "GCP Project:       ${GCP_PROJECT}"
log_info "Spanner:           ${SPANNER_INSTANCE}/${SPANNER_DB}"
log_info "Workers:           ${WORKER_COUNT}"
log_info "Runs/scenario:     ${RUN_COUNT}"
log_info "Scenario filter:   ${SCENARIO_FILTER:-ALL}"
log_info "Dry-run:           ${DRY_RUN:-false}"
log_info "Log directory:     ${LOG_DIR}"
echo ""

# ─── Python environment check ─────────────────────────────────────────────────

log_info "Checking Python environment..."
PYTHON_BIN="${VIRTUAL_ENV:+${VIRTUAL_ENV}/bin/python}"
PYTHON_BIN="${PYTHON_BIN:-$(which python3)}"

if ! "$PYTHON_BIN" -c "import asyncio, pathlib, uuid, dataclasses" 2>/dev/null; then
    log_fail "Python environment check failed — is the venv active?"
    exit 1
fi
log_ok "Python environment: $("$PYTHON_BIN" --version)"

# ─── Pre-flight cost check ─────────────────────────────────────────────────────

log_info "Running pre-flight cost attribution estimate..."
"$PYTHON_BIN" - << 'PYEOF'
import sys
sys.path.insert(0, '/Users/bmatonte/agent-memory-graph/.worktree/campaign-validation/E7-prep')
from cost_controller import CostAttributionEngine
engine = CostAttributionEngine()
estimate = engine.estimate_campaign_cost()
print(f"  LLM inference estimate:  ${estimate['llm_inference_total_usd']:.4f}")
print(f"  Total (w/ overhead):     ${estimate['grand_total_estimate_usd']:.4f}")
print(f"  Hard-stop threshold:     $260.00")
PYEOF
echo ""

# ─── Launch benchmarks ────────────────────────────────────────────────────────

log_info "Launching benchmark orchestrator..."
"$PYTHON_BIN" - << PYEOF
import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import UTC, datetime

sys.path.insert(0, '/Users/bmatonte/agent-memory-graph/.worktree/campaign-validation/E7-prep')
sys.path.insert(0, '/Users/bmatonte/agent-memory-graph')

from benchmark_runners import BenchmarkOrchestrator, SCENARIO_CATALOG, BatchResult
from cost_controller import CostLedger, HardStopPolicy, CostAttributionEngine

DRY_RUN = "${DRY_RUN}" == "--dry-run"
SCENARIO_FILTER = "${SCENARIO_FILTER}"
RUN_COUNT = int("${RUN_COUNT}")
WORKER_COUNT = int("${WORKER_COUNT}")
LOG_DIR = Path("${LOG_DIR}")

scenarios = list(SCENARIO_CATALOG.values())
if SCENARIO_FILTER:
    scenarios = [s for s in scenarios if s.scenario_id == SCENARIO_FILTER]
    if not scenarios:
        print(f"ERROR: Scenario '{SCENARIO_FILTER}' not found in catalog", file=sys.stderr)
        sys.exit(1)

ledger = CostLedger()
policy = HardStopPolicy()
attribution = CostAttributionEngine()
stop_event = asyncio.Event()

async def run_with_cost_monitoring():
    orchestrator = BenchmarkOrchestrator(
        scenarios=scenarios,
        run_count=RUN_COUNT,
        worker_count=WORKER_COUNT,
        dry_run=DRY_RUN,
        run_log_dir=LOG_DIR,
        stop_event=stop_event,
    )

    print(f"[LAUNCH] Starting {len(scenarios)} scenario(s), {RUN_COUNT} runs each, {WORKER_COUNT} workers")
    print(f"[LAUNCH] Dry-run mode: {DRY_RUN}")
    print("")

    batch_results = await orchestrator.run_all()

    # Record costs from batch results
    for scenario_id, batch in batch_results.items():
        for result in batch.results:
            if not result.warmup_flag:
                ledger.record(
                    run_id=result.run_id,
                    scenario_id=result.scenario_id,
                    agent_id=result.agent_id,
                    tokens_input=result.tokens_input,
                    tokens_output=result.tokens_output,
                    model_name=result.model_name,
                    estimated_cost_usd=result.estimated_cost_usd,
                )
        decision = policy.evaluate(ledger.total_spent())
        if decision.value == "stop":
            print(f"[HARD-STOP] Cost limit reached: \${ledger.total_spent():.4f}")
            stop_event.set()
            break

    # Print summary
    print("")
    print("=" * 60)
    print("BENCHMARK EXECUTION SUMMARY")
    print("=" * 60)
    for sid, batch in sorted(batch_results.items()):
        success_rate = batch.success_count / max(batch.measured_runs, 1)
        print(
            f"  {sid}: {batch.measured_runs} runs | "
            f"success={success_rate:.1%} | "
            f"groundedness={batch.avg_groundedness:.3f} | "
            f"p95={batch.p95_latency_ms:.0f}ms | "
            f"cost=\${batch.total_cost_usd:.4f}"
        )

    cost_summary = ledger.summary()
    print("")
    print(f"  Total measured runs:   {ledger.run_count()}")
    print(f"  Total cost:            \${cost_summary['total_spent_usd']:.4f}")
    print(f"  Budget utilization:    {cost_summary['utilization_pct']:.1f}% of \$260")
    print(f"  Remaining budget:      \${cost_summary['remaining_budget_usd']:.4f}")
    print("=" * 60)

    # Write summary JSON
    summary = {
        "campaign_id": "amg-campaign-2026-06-29",
        "execution_timestamp_utc": datetime.now(UTC).isoformat(),
        "dry_run": DRY_RUN,
        "scenarios_executed": len(batch_results),
        "cost_summary": cost_summary,
        "batch_results": {
            sid: {
                "measured_runs": b.measured_runs,
                "success_rate": b.success_count / max(b.measured_runs, 1),
                "avg_groundedness": b.avg_groundedness,
                "p95_latency_ms": b.p95_latency_ms,
                "total_cost_usd": b.total_cost_usd,
            }
            for sid, b in batch_results.items()
        },
    }
    Path("${SUMMARY_FILE}").write_text(json.dumps(summary, indent=2))
    print(f"\n[OK] Summary written to: ${SUMMARY_FILE}")
    return cost_summary["total_spent_usd"]

total_spent = asyncio.run(run_with_cost_monitoring())
if total_spent >= 260.0:
    sys.exit(2)  # hard-stop exit code
sys.exit(0)
PYEOF

EXIT_CODE=$?

echo ""
if [[ $EXIT_CODE -eq 2 ]]; then
    log_warn "Benchmark execution halted by cost hard-stop."
    log_warn "Final spend >= \$260. No new runs will start."
    log_warn "Proceeding to E7-exec-T9 gate with available data."
    exit 0  # not a script error; proceed to gate
elif [[ $EXIT_CODE -ne 0 ]]; then
    log_fail "Benchmark execution failed with exit code ${EXIT_CODE}."
    exit 1
else
    log_ok "Benchmark execution complete. See: ${SUMMARY_FILE}"
    log_ok "Proceed to E7-exec-T4 (Cost Monitoring) and E7-exec-T5 (Baselines)."
    exit 0
fi
