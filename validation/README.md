# Validation

GCP product validation campaign artifacts for the Cognitive Agent Memory Graph.

## Structure

```
validation/
  campaign/
    campaign-plan.md            — GCP Product Validation Campaign Plan (source of truth)
    backlog.md                  — Full epic/task backlog (E1–E8)
    artifacts/                  — Frozen design artifacts (E1-T1 through E6-T7)
    gates/                      — Signed gate reports (W1–W6a)
    E7-prep/                    — Benchmark preparation modules (offline, no GCP required)
      benchmark_runners.py      — ScenarioRunner, BenchmarkOrchestrator (12 EMC scenarios)
      statistics_engine.py      — KPI scoring, confidence intervals, effect sizes (Plan §13)
      cost_controller.py        — CostLedger, HardStopPolicy ($260 hard stop)
      observability_templates.yaml — Cloud Logging/Trace/Monitoring deployment templates
      report_template.md        — Executive report with placeholders for E8 infill
      failure_taxonomy.md       — 18 failure categories with rerun eligibility
      rerun_eligibility_rules.yaml — Machine-readable rerun rules for E7-exec-T7
      E7-exec-launch-checklist.md  — Operational launch checklist for 2026-07-23
      scripts/
        validate_infrastructure.sh  — GCP health checks (run at 00:00 UTC launch day)
        deploy_observability.sh     — Deploy logging sinks, trace, monitoring
        launch_benchmarks.sh        — Execute all 12 scenarios with cost control
      tests/
        test_e7_prep_dryrun.py  — 52 offline tests, no GCP access required
```

## Current Status

| Epic | Status | Date |
|------|--------|------|
| E1 Campaign Framing | Done | 2026-07-08 |
| E2 Security Design | Done | 2026-07-08 |
| E3 Data Design | Done | 2026-07-08 |
| E4 Benchmark Design | Done | 2026-07-08 |
| E5 GCP Bootstrap | Done | 2026-07-09 |
| E6 Data Provisioning | Done | 2026-07-09 |
| E7-prep Offline Preparation | Done | 2026-07-09 |
| E7-exec Benchmark Execution | Pending — launch 2026-07-23 |
| E8 Analysis & Closure | Pending — 2026-07-27 |

## Running E7-prep Tests (Offline)

```bash
uv run pytest validation/campaign/E7-prep/tests/ -v
```

Expected: **52 passed**, 0 errors, no GCP access required.

## Launch Day (2026-07-23)

```bash
# 1. Validate infrastructure (00:00 UTC, 1 hour)
validation/campaign/E7-prep/scripts/validate_infrastructure.sh

# 2. Deploy observability (01:00 UTC, 1 hour)
validation/campaign/E7-prep/scripts/deploy_observability.sh

# 3. Launch benchmarks (02:00 UTC onwards, 4 days)
validation/campaign/E7-prep/scripts/launch_benchmarks.sh
```

See [E7-exec-launch-checklist.md](campaign/E7-prep/E7-exec-launch-checklist.md) for full step-by-step guide.
