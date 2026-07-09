# Epic E7 Restructure: Defer GCP Infrastructure to Same-Day Launch

**Effective Date:** 2026-07-09
**Campaign Kickoff Remains:** 2026-07-23
**Principle:** Maximize offline preparation; access GCP infrastructure only for final benchmark launch window

---

## The Problem with Original E7

Original Epic E7 assumed:
- E6 (infrastructure provisioning) complete → infrastructure live for weeks
- E7 (benchmark execution) would access live infrastructure immediately
- Risk: Infrastructure configuration drift, cost accumulation, integration staleness during 2-week buffer

New approach:
- **E7-prep** (Weeks 1-2): Build ALL offline components (runners, stats engine, observability, cost tracking, templates)
- **E7-exec** (Week 3, same day): Validate infrastructure (1 hour), deploy observability (1 hour), launch benchmarks immediately
- **Result**: Minimal GCP resource lifetime (4 days only), zero drift, controlled cost burn

---

## New Epic Structure

### Epic E7-prep: Offline Preparation (2026-07-09 to 2026-07-22)

**Objective:** Build all benchmark infrastructure offline, ready for same-day launch.

**9 Tasks (all runnable in parallel, zero GCP access required):**

| Task | Deliverable | Estimate | Dependency |
|------|-------------|----------|-----------|
| E7-prep-T1 | `benchmark_runners.py` (ScenarioRunner, BenchmarkOrchestrator) + dry-run tests | L (3-4 days) | E4-T2, E6-T6 |
| E7-prep-T2 | `statistics_engine.py` (KPI scoring, confidence intervals) + unit tests | M (2-3 days) | E4-T5 |
| E7-prep-T3 | `observability_templates.yaml` (logging, tracing, monitoring) + deploy script | M (2-3 days) | E5-T6 |
| E7-prep-T4 | `cost_controller.py` (CostLedger, HardStopPolicy) + unit tests | M (2-3 days) | E4-T6, E5-T4 |
| E7-prep-T5 | Report templates (markdown, JSON, xlsx) + visualization specs | M (2-3 days) | E4-T7 |
| E7-prep-T6 | `agent_path_validation_report.md` (scenario → code mapping) | M (2-3 days) | E4-T2, src/agents/ |
| E7-prep-T7 | `failure_taxonomy.md` + `rerun_eligibility_rules.yaml` | M (2-3 days) | E4-T5, E6-T6 |
| E7-prep-T8 | `E7-exec-launch-checklist.md`, `deploy_observability.sh`, `launch_benchmarks.sh` | S (1 day) | E7-prep-T1-T7 |
| E7-prep-T9 | **Week 2 Offline Readiness Gate** (all offline work complete, "ready to launch") | S (0.5 day) | E7-prep-T1-T8 |

**Gate Criteria for E7-prep-T9:**
- [ ] benchmark_runners.py complete with dry-run tests passing
- [ ] statistics_engine.py complete with unit tests passing
- [ ] observability_templates.yaml complete + deploy script tested
- [ ] cost_controller.py complete with unit tests passing
- [ ] Report templates complete + visualization specs validated
- [ ] Agent code paths traced and validated against scenarios
- [ ] Failure taxonomy defined + rerun rules documented
- [ ] Launch automation scripts complete and tested (dry-run on local code)
- [ ] All deliverables staged in `.worktree/campaign-validation/E7-prep/`
- [ ] **6/6 stakeholder approvals** (same team as E6 gate)

**Expected Outcome:** 2026-07-22, 100% offline prep complete, "ready to flip the switch" authorization.

---

### Epic E7-exec: Same-Day Launch & Execution (2026-07-23 to 2026-07-27)

**Objective:** Validate infrastructure (1 hour), deploy observability (1 hour), execute 400+ benchmarks immediately.

**9 Tasks (sequential with tight time windows):**

| Task | Window | Deliverable | Duration |
|------|--------|-------------|----------|
| E7-exec-T1 | 2026-07-23 00:00-01:00 UTC | Infrastructure validation report (all systems green) | 1 hour |
| E7-exec-T2 | 2026-07-23 01:00-02:00 UTC | Observability deployment confirmation (dashboards live) | 1 hour |
| E7-exec-T3 | 2026-07-23 02:00 → 2026-07-27 23:00 UTC | Raw run logs + token tracking (320+ mandatory runs) | ~4 days |
| E7-exec-T4 | Continuous during T3 | Cost ledger + hard-stop decision log | Continuous |
| E7-exec-T5 | After E7-exec-T3 baseline complete | Baseline comparison dataset | ~1 day |
| E7-exec-T6 | Post E7-exec-T3 | Failure taxonomy report + rerun eligibility log | ~6 hours |
| E7-exec-T7 | If instability detected | Rerun evidence log | Variable |
| E7-exec-T8 | If budget allows | Extended scenario results | Variable |
| E7-exec-T9 | 2026-07-27 22:00 UTC (pre-TTL) | **Week 3 Execution Gate** (benchmarks complete, cost finalized) | 1 hour |

**Gate Criteria for E7-exec-T9:**
- [ ] Infrastructure validation passed (Spanner, BigQuery, GCS, Cloud Run, integrations all healthy)
- [ ] 320+ mandatory runs executed and logged
- [ ] Baseline runs executed under identical constraints
- [ ] Tokens tracked for all runs (cost attribution complete)
- [ ] Cost ≤ $260 hard-stop limit
- [ ] Failure taxonomy applied, reruns justified
- [ ] All data ingested to `benchmark_metrics.runs` table
- [ ] Observability dashboards collected + links documented
- [ ] **Ready for post-execution analysis (E8)**

**Expected Outcome:** 2026-07-27, all benchmark data collected, cost finalized, ready for analysis.

---

### Epic E8: Post-Execution Analysis & Cleanup (2026-07-27 onwards)

**Objective:** Compute statistics, generate decision package, tear down infrastructure, verify cleanup.

**8 Tasks (compressed, must complete by 2026-07-27 23:59 UTC):**

| Task | Deliverable | Owner |
|------|-------------|-------|
| E8-T1 | Statistical appendix (confidence intervals, effect sizes) | Data Lead |
| E8-T2 | Decision matrix (pass/fail against acceptance criteria) | Program Manager |
| E8-T3 | Final benchmark report + go/no-go recommendation + residual risk | Program Manager |
| E8-T4 | Teardown checklist + protected resource denylist | Infrastructure Lead |
| E8-T5 | Terraform destroy execution log (with approval record) | Infrastructure Lead |
| E8-T6 | Residual scan report (Terraform inventory + labels, target: zero resources) | Infrastructure Lead |
| E8-T7 | Billing verification (24h post-destroy, confirm no charges) | Finance Lead |
| E8-T8 | Closure package + post-campaign retrospective | Program Manager |

**Gate Criteria for E8 Closure:**
- [ ] Statistical analysis complete and reviewed
- [ ] Final recommendation approved by all stakeholders
- [ ] Terraform destroy executed and logged
- [ ] Zero residual GCP resources confirmed (inventory scan)
- [ ] Billing verification: no charges after destroy
- [ ] Campaign TTL auto-delete triggered successfully
- [ ] Closure artifacts archived

**Expected Outcome:** 2026-07-27 23:59 UTC, campaign TTL expires, all resources deleted, final report published.

---

## Timeline Summary

```
Week 1-2: E7-prep (Offline)
2026-07-09 ├─ E7-prep-T1 (benchmark_runners.py) ────────┐
           ├─ E7-prep-T2 (statistics_engine.py) ────────┤
           ├─ E7-prep-T3 (observability_templates.yaml) ├─ Parallel execution
           ├─ E7-prep-T4 (cost_controller.py) ──────────┤ All offline,
           ├─ E7-prep-T5 (report templates) ────────────┤ no GCP access
           ├─ E7-prep-T6 (agent_path_validation) ───────┤
           ├─ E7-prep-T7 (failure_taxonomy) ────────────┤
           ├─ E7-prep-T8 (launch automation) ───────────┘
           └─ E7-prep-T9 (Week 2 gate) → "READY TO LAUNCH"
              2026-07-22

Week 3: E7-exec (Same-Day Launch)
2026-07-23 ├─ E7-exec-T1 (validate infrastructure) ─── 1 hour
           ├─ E7-exec-T2 (deploy observability) ────── 1 hour
           ├─ E7-exec-T3 (execute benchmarks) ──────── 4 days
           ├─ E7-exec-T4 (monitor cost) ───────────── continuous
           ├─ E7-exec-T5 (run baselines) ──────────── 1 day
           ├─ E7-exec-T6 (classify failures) ──────── 6 hours
           ├─ E7-exec-T7 (execute reruns) ────────── variable
           ├─ E7-exec-T8 (extended scenarios) ────── variable
           └─ E7-exec-T9 (Week 3 gate) → "BENCHMARKS COMPLETE"
              2026-07-27 22:00 UTC

Week 4: E8 (Analysis & Cleanup)
2026-07-27 ├─ E8-T1 through E8-T3 (analysis & report) ── 6 hours
           ├─ E8-T4 through E8-T8 (cleanup) ────────── 18 hours
           └─ 2026-07-27 23:59 UTC → Campaign TTL auto-delete
```

---

## Advantages of Restructured Approach

### 1. **Maximize Offline Work (No GCP Risk During Prep)**
- 14 days of uninterrupted offline development
- Test benchmark runners locally with dry-run data
- Build statistical framework without depending on live infrastructure
- No risk of infrastructure misconfiguration affecting prep

### 2. **Minimize GCP Lifetime (Infrastructure Active Only 4 Days)**
- E6 provisioning: 2026-07-01 to 2026-07-22 (frozen, no changes)
- E7 active execution: 2026-07-23 to 2026-07-27 only
- E8 cleanup: 2026-07-27 to 2026-07-27 23:59 UTC (tear down immediately)
- Result: ~27 days of provisioned infrastructure → only 4-5 days of active execution

### 3. **Same-Day Launch (No Surprises)**
- 1 hour validation + 1 hour observability setup
- Benchmarks start same day (2026-07-23 02:00 UTC)
- All automation pre-tested
- All decision logic (failure taxonomy, rerun rules) pre-decided

### 4. **Cost Optimization**
- Minimal data aggregation/transformation during execution (pre-built templates)
- Cost controller running from benchmark start, hard-stop active
- No expensive last-minute changes or reruns due to prep delays

### 5. **Higher Confidence**
- Agent code paths traced before execution (E7-prep-T6)
- Statistical methods validated before data collection (E7-prep-T2)
- Report templates ready, data infill only (E7-prep-T5)
- Failure handling pre-decided (E7-prep-T7)

---

## Immediate Action Items (Starting 2026-07-09)

### Priority 1: Start E7-prep Tasks in Parallel

1. **E7-prep-T1 (Benchmark Runners)** → Start immediately
   - Review E4-T2 (benchmark scenarios) and E6-T6 (smoke tests) for measurement baseline
   - Create Python module: `src/benchmark_runners.py`
   - Classes: `ScenarioRunner`, `BenchmarkOrchestrator`, `MeasurementProtocol`
   - Dry-run test: Execute 10 fake runs locally, verify metrics collection
   - Owner: Backend Engineer

2. **E7-prep-T2 (Statistics Engine)** → Start immediately
   - Review E4-T5 (KPI definitions)
   - Create Python module: `src/statistics_engine.py`
   - Classes: `KPIScoringEngine`, `ConfidenceIntervalComputer`, `EffectSizeAnalyzer`
   - Unit tests: Mock data, verify confidence interval computation
   - Owner: Data Lead

3. **E7-prep-T3 (Observability Templates)** → Start immediately
   - Design Cloud Logging queries (trace filtering, latency aggregation)
   - Design Cloud Trace span hierarchies (parent/child for agent calls)
   - Design Cloud Monitoring dashboards (latency p95, token count, cost per run)
   - Create YAML template: `.worktree/campaign-validation/E7-prep/observability_templates.yaml`
   - Create deployment script: `deploy_observability.sh`
   - Owner: Infrastructure Lead

4. **E7-prep-T4 (Cost Controller)** → Start immediately
   - Review E4-T6 (cost model) and E5-T4 (billing integration)
   - Create Python module: `src/cost_controller.py`
   - Classes: `CostLedger`, `HardStopPolicy`, `CostAttributionEngine`
   - Unit tests: Mock spending, verify hard-stop triggers at $260
   - Owner: Finance Lead

5. **E7-prep-T5 (Report Templates)** → Start immediately
   - Draft report structure (executive summary, tables, recommendations)
   - Markdown template: `.worktree/campaign-validation/E7-prep/report_template.md`
   - Visualization specs: `.worktree/campaign-validation/E7-prep/visualization_specs.json` (Plotly configs)
   - Decision matrix template: `.worktree/campaign-validation/E7-prep/decision_matrix_template.xlsx`
   - Owner: Program Manager

6. **E7-prep-T6 (Agent Path Validation)** → Start immediately
   - Review E4-T2 scenarios and agent code
   - Trace execution paths for each scenario
   - Document expected result ranges
   - Create report: `.worktree/campaign-validation/E7-prep/agent_path_validation_report.md`
   - Owner: Backend Engineer

7. **E7-prep-T7 (Failure Taxonomy)** → Start immediately
   - Define 10-15 failure categories
   - Specify statistical criteria for reruns
   - Create `failure_taxonomy.md` and `rerun_eligibility_rules.yaml`
   - Owner: Data Lead + Program Manager

8. **E7-prep-T8 (Launch Automation)** → Start once T1-T7 provide outputs
   - Create checklist: `.worktree/campaign-validation/E7-prep/E7-exec-launch-checklist.md`
   - Create scripts: `deploy_observability.sh`, `validate_infrastructure.sh`, `launch_benchmarks.sh`
   - Owner: Infrastructure Lead

### Priority 2: Prepare E7-prep-T9 Gate (Target: 2026-07-22)

- Verify all 8 tasks complete
- Run through launch automation scripts in dry-run mode
- Prepare gate report (24 criteria checklist)
- Obtain 6 stakeholder sign-offs

### Priority 3: Prepare E7-exec Automation (Target: 2026-07-23 00:00 UTC)

- Stage all scripts in `.worktree/campaign-validation/E7-exec/`
- Run E7-exec-T1 (infrastructure validation) at 2026-07-23 00:00 UTC
- Run E7-exec-T2 (observability deployment) at 2026-07-23 01:00 UTC
- Launch benchmarks at 2026-07-23 02:00 UTC

---

## Resource Allocation

All 9 E7-prep tasks can run in parallel (independent codebases and templates). Recommended team structure:

| Owner | Tasks | Focus |
|-------|-------|-------|
| Backend Engineer | E7-prep-T1, E7-prep-T6 | Runners, agent validation |
| Data Lead | E7-prep-T2, E7-prep-T7 | Stats, failure taxonomy |
| Infrastructure Lead | E7-prep-T3, E7-prep-T8 | Observability, automation |
| Finance Lead | E7-prep-T4 | Cost controller |
| Program Manager | E7-prep-T5, E7-prep-T9 | Report templates, gate |

**Estimated Effort:** 2 weeks, 9 FTE-days distributed across team.

---

## Success Criteria (2026-07-22 Gate)

✅ Benchmark runner framework complete + dry-run tests passing
✅ Statistical analysis engine complete + unit tests passing
✅ Observability templates pre-built + deploy script tested
✅ Cost controller complete + hard-stop policy verified
✅ Report templates ready + visualization specs validated
✅ Agent code paths traced + scenarios validated
✅ Failure taxonomy documented + rerun rules clear
✅ Launch automation scripts complete + dry-run passing
✅ All deliverables staged in `.worktree/campaign-validation/E7-prep/`
✅ **6/6 stakeholder sign-offs** (Data, Infrastructure, Backend, Security, Finance, Program Manager)

**Gate Decision:** ✅ **GO to E7-exec** (same-day launch authorization)

---

**Prepared by:** Campaign Planning Team
**Date:** 2026-07-09
**Classification:** Campaign-Internal
