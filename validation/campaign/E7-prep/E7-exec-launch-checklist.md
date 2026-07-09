# E7-exec Launch Checklist
# Owner: Infrastructure Lead + Program Manager
# Use on: 2026-07-23 starting 00:00 UTC

**Campaign:** amg-campaign-2026-06-29
**Launch Date:** 2026-07-23
**TTL Deadline:** 2026-07-27 23:59 UTC

---

## PRE-LAUNCH (Complete before 00:00 UTC)

### E7-prep verification (complete by 2026-07-22 18:00 UTC)

- [ ] E7-prep-T9 gate report signed (all 24 criteria PASS, 6/6 stakeholder approvals)
- [ ] All E7-prep deliverables staged in `.worktree/campaign-validation/E7-prep/`
- [ ] Dry-run tests passing locally: `pytest .worktree/campaign-validation/E7-prep/tests/ -v` → 49/49 PASS
- [ ] All scripts executable: `ls -la .worktree/campaign-validation/E7-prep/scripts/*.sh`
- [ ] Scripts syntax-checked: `bash -n scripts/validate_infrastructure.sh && bash -n scripts/deploy_observability.sh && bash -n scripts/launch_benchmarks.sh`

### Environment readiness

- [ ] Python venv active: `source .venv/bin/activate`
- [ ] GCP auth valid: `gcloud auth list --filter=status:ACTIVE`
- [ ] Correct project: `gcloud config get-value project` → `amg-validation-2026-07-q3`
- [ ] Environment variables set:
  - [ ] `GCP_PROJECT_ID=amg-validation-2026-07-q3`
  - [ ] `SPANNER_INSTANCE_ID=amg-campaign-spanner`
  - [ ] `SPANNER_DATABASE_ID=memory_db`
  - [ ] `BENCHMARK_WORKERS=4`
  - [ ] `BENCHMARK_RUNS_PER_SCENARIO=30`

### Team on-call confirmed

- [ ] Backend Engineer (D. Williams) — on-call for runners/agent path issues
- [ ] Data Lead (J. Patel) — on-call for KPI monitoring
- [ ] Infrastructure Lead (T. Chen) — on-call for GCP health
- [ ] Finance Lead (M. Rodriguez) — on-call for cost monitoring
- [ ] Program Manager (S. Gupta) — on-call for decisions

---

## LAUNCH WINDOW (2026-07-23 00:00 to 02:00 UTC)

### T1: Infrastructure Validation (00:00–01:00 UTC)

```bash
cd /Users/bmatonte/agent-memory-graph
source .venv/bin/activate
.worktree/campaign-validation/E7-prep/scripts/validate_infrastructure.sh
```

- [ ] Script exits 0 (all checks passed)
- [ ] Report generated: `.worktree/campaign-validation/artifacts/E7-exec-infrastructure-validation-report.md`
- [ ] Spanner instance READY, node count ≥ 100 ✓
- [ ] BigQuery datasets accessible: raw_retail_public, curated_retail_campaign, benchmark_metrics ✓
- [ ] GCS corpus accessible: ≥ 1,000 documents ✓
- [ ] Cloud Run service READY, health endpoint 200 OK ✓
- [ ] All 4 integration secrets present in Secret Manager ✓
- [ ] Freeze manifest exists in GCS ✓

**DECISION:** ☐ PROCEED to T2 | ☐ HALT (fix failures, re-run script)

If HALT: Contact Infrastructure Lead (T. Chen) immediately.

---

### T2: Deploy Observability (01:00–02:00 UTC)

```bash
.worktree/campaign-validation/E7-prep/scripts/deploy_observability.sh
```

- [ ] Script exits 0 (all deployments successful)
- [ ] Log sink `amg-benchmark-runs-sink` created and active
- [ ] Log sink `amg-audit-events-sink` created and active
- [ ] Cloud Trace sampling rate set to 1.0 (100%) on Cloud Run
- [ ] Cost hard-stop alert policy created
- [ ] Dashboard URLs documented:
  - Logs: _______________________________________________
  - Trace: _______________________________________________
  - Cloud Run: _______________________________________________

**DECISION:** ☐ PROCEED to T3 | ☐ HALT (fix failures, re-run script)

---

### T3: Launch Benchmark Execution (02:00 UTC onwards)

```bash
# Option A: Full campaign (all 12 scenarios)
.worktree/campaign-validation/E7-prep/scripts/launch_benchmarks.sh

# Option B: Single scenario test (first verify one scenario works)
.worktree/campaign-validation/E7-prep/scripts/launch_benchmarks.sh --scenario EMC-001
```

- [ ] Orchestrator spawned (log line: `[LAUNCH] Starting 12 scenario(s)`)
- [ ] First 10 runs logged to `/tmp/amg_benchmark_runs/*.jsonl`
- [ ] First 10 runs show task_success and groundedness values
- [ ] No immediate errors in first 5 minutes
- [ ] Cost ledger recording: `cat /tmp/amg_benchmark_runs/cost_ledger.jsonl | head -5`

**DECISION:** ☐ CONTINUE (benchmarks running normally) | ☐ ROLLBACK (critical error in first 10 runs)

---

## DURING EXECUTION (Every 12 hours: 14:00 UTC, 02:00+1 UTC, etc.)

### Cost Monitoring Check

```bash
python3 -c "
import json, pathlib
log = pathlib.Path('/tmp/amg_benchmark_runs/execution_summary.json')
if log.exists():
    s = json.loads(log.read_text())
    print(f'Total spent: \${s[\"cost_summary\"][\"total_spent_usd\"]:.4f}')
    print(f'Remaining:   \${s[\"cost_summary\"][\"remaining_budget_usd\"]:.4f}')
    print(f'Utilization: {s[\"cost_summary\"][\"utilization_pct\"]:.1f}%')
"
```

- [ ] Check: `total_spent_usd` < $200 (PROCEED) / $200-$239 (WARN_1) / $240-$259 (WARN_2) / ≥$260 (STOP)
- [ ] Update cost tracking log

### Run Progress Check

```bash
# Count completed runs by scenario
for f in /tmp/amg_benchmark_runs/EMC-*.jsonl; do
    echo "$(basename $f .jsonl): $(wc -l < $f) runs"
done
```

- [ ] Progress toward 30 measured runs per scenario
- [ ] No scenario stuck at 0 runs (would indicate systematic failure)

### Error Rate Check

```bash
# Count failures by outcome
python3 -c "
import json, pathlib, collections
logs_dir = pathlib.Path('/tmp/amg_benchmark_runs')
outcomes = collections.Counter()
for f in logs_dir.glob('EMC-*.jsonl'):
    for line in f.read_text().splitlines():
        r = json.loads(line)
        if not r.get('warmup_flag'):
            outcomes[r.get('outcome', 'unknown')] += 1
total = sum(outcomes.values())
for outcome, cnt in outcomes.most_common():
    print(f'  {outcome}: {cnt} ({cnt/max(total,1):.1%})')
"
```

- [ ] `success` rate ≥ 70% of completed measured runs
- [ ] No `AF-005` (isolation violation) — if found, HALT EMC-004 immediately
- [ ] No `SYS-003` (config hash mismatch) — if found, HALT ALL immediately

---

## LAUNCH WINDOW CLOSURE (2026-07-27 20:00–22:00 UTC, pre-TTL)

- [ ] All 12 scenarios completed 30 measured runs (or cost hard-stop triggered)
- [ ] All baseline runs complete (E7-exec-T5)
- [ ] Failure taxonomy applied to all failed runs (E7-exec-T6)
- [ ] Approved reruns executed (E7-exec-T7)
- [ ] Cost ledger finalized
- [ ] Final cost: $_____________ (within $260 limit)
- [ ] Execution summary written: `/tmp/amg_benchmark_runs/execution_summary.json`
- [ ] Begin E7-exec-T9 gate report preparation

**DECISION:** ☐ Data ready for E8 analysis | ☐ Issues requiring resolution before E8

---

## ROLLBACK PROCEDURE

If critical failure in T1 or T2 (infrastructure issues):

1. Stop all benchmark processes
2. Do NOT modify any infrastructure (freeze is in place)
3. Contact Infrastructure Lead (T. Chen)
4. Document failure in `.worktree/campaign-validation/artifacts/E7-exec-infrastructure-validation-report.md`
5. Attempt re-run after root cause is identified (max delay: 4 hours before TTL concern)

If AF-005 (data isolation violation) detected:

1. **Stop EMC-004 scenario immediately** (`kill` benchmark process for EMC-004 only)
2. Contact Security Lead (A. Kumar) — IMMEDIATE
3. Do NOT rerun EMC-004 until Security Lead confirms
4. Continue other 11 scenarios

If SYS-001 (cost hard-stop):

1. `stop_event` is set automatically by BenchmarkOrchestrator
2. Allow in-progress runs to complete
3. Log all pending runs as cancelled
4. Notify Finance Lead (M. Rodriguez) and Program Manager (S. Gupta)
5. Proceed to E7-exec-T9 gate with available data

---

## CONTACTS

| Role | Name | Action |
|------|------|--------|
| Infrastructure Lead | T. Chen | T1/T2 failures, INF-001, INF-003 |
| Backend Engineer | D. Williams | AF-006, INF-003, runner issues |
| Data Lead | J. Patel | AF-003, AF-004, INF-002, KPI concerns |
| Security Lead | A. Kumar | AF-005, SYS-003 |
| Finance Lead | M. Rodriguez | SYS-001, cost monitoring |
| Program Manager | S. Gupta | Final decisions, IF-001, SYS-002 |
