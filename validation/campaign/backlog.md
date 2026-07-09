# Campaign Validation Backlog

Source plan: GCP Product Validation Campaign Plan
Scope: 6-week validation campaign with mandatory and extended tracks

## Backlog Operating Rules

- Priority scale: P0 (critical), P1 (high), P2 (medium)
- Status: Todo, In Progress, Blocked, Done
- Estimation: S (<=1 day), M (2-3 days), L (4-5 days)
- Definition of Done (DoD): task output is stored in campaign artifacts and reviewed by owner

## Sequencing Override

- Corporate GCP identifiers and billing metadata are expected late.
- Offline-ready planning, governance, security, data design, and benchmark design must complete before any task depends on concrete GCP values.
- Cloud bootstrap, budget activation, runtime provisioning, and resource-backed validation are deferred until the latest safe point before benchmark execution.

## Epic E1 - Campaign Framing and Offline Readiness

Objective:

- Freeze campaign structure, governance, and evidence flow without requiring live GCP inputs.

Success criteria:

- The campaign can progress through Week 3 without `PROJECT_ID`, `BILLING_ACCOUNT_ID`, or `REGION`.
- Deferred-input placeholders and unresolved-input tracking are defined.
- The Week 1 gate is based on design readiness rather than cloud provisioning.

Tasks:

- E1-T1 Re-baseline campaign sequencing around delayed GCP inputs
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 1
  - Dependencies: none
  - Deliverable: approved sequencing decision note and updated backlog

- E1-T2 Define campaign artifact model, evidence register, and workstream ownership
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 1
  - Dependencies: E1-T1
  - Deliverable: artifact index, evidence register, and RACI matrix

- E1-T3 Draft placeholder variable contract and unresolved-input register (`PROJECT_ID`, `BILLING_ACCOUNT_ID`, `REGION`, dates)
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 1
  - Dependencies: E1-T1
  - Deliverable: placeholder variable contract and unresolved-input register

- E1-T4 Prepare backend/workspace strategy template independent of concrete GCP identifiers
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 1
  - Dependencies: E1-T3
  - Deliverable: backend config template, workspace strategy, and naming convention

- E1-T5 Define campaign label policy, naming convention, and artifact folder structure
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 1
  - Dependencies: E1-T2
  - Deliverable: label policy and naming standard

- E1-T6 Publish offline validation runbook and Week 1 design gate review
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 1
  - Dependencies: E1-T2,E1-T3,E1-T4,E1-T5
  - Deliverable: offline runbook and signed Week 1 design gate report

## Epic E2 - Security, Agent, and Integration Design Readiness

Objective:

- Finalize least-privilege design, agent boundaries, and integration prerequisites before any cloud provisioning.

Success criteria:

- IAM and secret-handling design is approved without requiring deployed resources.
- Mandatory agent scopes and integration prerequisites are frozen.

Tasks:

- E2-T1 Build campaign IAM matrix by agent and integration
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 1-2
  - Dependencies: E1-T3
  - Deliverable: IAM matrix with allow and deny actions

- E2-T2 Define mandatory agent profiles, policy boundaries, allowed tools, memory tiers, and denied actions
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 1-2
  - Dependencies: E2-T1
  - Deliverable: approved agent profile catalog

- E2-T3 Define secret inventory, credential ownership, and access policy model
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 2
  - Dependencies: E2-T1
  - Deliverable: secret inventory and access policy design

- E2-T4 Document mandatory integration prerequisites (Slack, Calendar, Jira, GitHub)
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 2
  - Dependencies: E2-T2
  - Deliverable: integration prerequisite catalog and configuration checklist

- E2-T5 Prepare authz denial and privilege escalation smoke plan
  - Status: Done
  - Priority: P1
  - Estimate: S
  - Week: 2
  - Dependencies: E2-T3,E2-T4
  - Deliverable: security smoke test plan and expected outcomes

- E2-T6 Week 2 security and access design gate review
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 2
  - Dependencies: E2-T1,E2-T2,E2-T3,E2-T4,E2-T5
  - Deliverable: security and access design gate report

## Epic E3 - Data Design, Fixtures, and Provenance Preparation

Objective:

- Prepare public and synthetic data assets, graph fixtures, and quality criteria before cloud resources exist.

Success criteria:

- Data designs, provenance, and validation rules are ready to materialize once GCP bootstrap starts.
- No Week 2 task depends on BigQuery, GCS, or Spanner provisioning.

Tasks:

- E3-T1 Define canonical schema map for retail domains
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 2
  - Dependencies: E1-T2
  - Deliverable: schema map and entity relationship matrix

- E3-T2 Select and register structured public and synthetic source datasets
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 2
  - Dependencies: E3-T1
  - Deliverable: source inventory with expected load targets

- E3-T3 Prepare text corpus manifest and metadata tagging schema
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 2
  - Dependencies: E3-T1
  - Deliverable: corpus manifest with source, date, and sensitivity metadata rules

- E3-T4 Define Spanner graph seed specification and no-evidence scenario fixtures
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 2
  - Dependencies: E3-T1
  - Deliverable: graph seeding spec, counts target, and no-evidence fixtures

- E3-T5 Define data quality gates (referential, nulls, cardinality, distributions, connectivity)
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 2
  - Dependencies: E3-T2,E3-T3,E3-T4
  - Deliverable: DQ scorecard template with thresholds and validation queries

- E3-T6 Complete provenance and licensing register
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 2
  - Dependencies: E3-T2,E3-T3
  - Deliverable: approved provenance register with license type, allowed use, and attribution records

- E3-T7 Week 2 data design gate review
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 2
  - Dependencies: E3-T1,E3-T2,E3-T3,E3-T4,E3-T5,E3-T6
  - Deliverable: signed Week 2 data design gate report

## Epic E4 - Benchmark, Observability, and Cost Control Design

Objective:

- Build the benchmark protocol, observability contract, and cost-control model before cloud provisioning.

Success criteria:

- Benchmark and KPI definitions are fully specified before Week 4.
- Observability and cost-control designs are execution-ready when GCP identifiers arrive.

Tasks:

- E4-T1 Create benchmark catalog with `scenario_id`, pass rules, no-evidence cases, and sample-size plan
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 2-3
  - Dependencies: E2-T2,E3-T4
  - Deliverable: benchmark catalog v1

- E4-T2 Define scoring rubric for task success and groundedness
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 3
  - Dependencies: E4-T1
  - Deliverable: scoring rubric and adjudication protocol

- E4-T3 Implement run manifest schema (`run_id`, seed, versions, config hash)
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 3
  - Dependencies: E4-T1
  - Deliverable: reproducibility manifest template with seed, model version, prompt version, and config hash

- E4-T4 Define observability event schema, trace plan, audit capture points, and metrics ingestion contract
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 3
  - Dependencies: E4-T2,E4-T3
  - Deliverable: observability and metrics design pack

- E4-T5 Validate KPI formulas and SQL templates for the future `benchmark_metrics` dataset
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 3
  - Dependencies: E4-T4
  - Deliverable: validated KPI SQL templates and test logic

- E4-T6 Prepare cost ledger template, burn forecast method, and hard-stop decision workflow
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 3
  - Dependencies: E4-T2
  - Deliverable: cost control ledger template and escalation workflow

- E4-T7 Dry-run benchmark protocol on local or synthetic fixtures with warm-up exclusion check
  - Status: Done
  - Priority: P1
  - Estimate: S
  - Week: 3
  - Dependencies: E4-T5,E4-T6
  - Deliverable: dry-run report and protocol fixes

- E4-T8 Week 3 benchmark and observability design gate review
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 3
  - Dependencies: E4-T1,E4-T2,E4-T3,E4-T4,E4-T5,E4-T6,E4-T7
  - Deliverable: signed Week 3 protocol gate report

## Epic E5 - Deferred GCP Bootstrap and Runtime Provisioning

Objective:

- Bootstrap the campaign environment only after offline design work is complete and concrete GCP identifiers arrive.

Success criteria:

- Terraform workspace applies successfully.
- Budget and monitoring controls are active.
- Campaign labels and ownership metadata are enforced on provisioned resources.

Tasks:

- E5-T1 Confirm concrete variable contract (`PROJECT_ID`, `BILLING_ACCOUNT_ID`, `REGION`, dates)
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 4
  - Dependencies: E1-T3,E4-T8
  - Deliverable: approved concrete variable contract with billing linkage confirmation

- E5-T2 Initialize Terraform backend and campaign workspace strategy
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 4
  - Dependencies: E5-T1
  - Deliverable: backend config and activated campaign workspace

- E5-T3 Enable required APIs and verify Artifact Registry and service readiness
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 4
  - Dependencies: E5-T2
  - Deliverable: API enablement checklist with readiness evidence

- E5-T4 Configure campaign budget alerts and burn monitoring
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 4
  - Dependencies: E5-T1
  - Deliverable: active alerts at 50/75/90/100% and daily burn ledger initialization

- E5-T5 Configure service accounts, required role bindings, and Secret Manager
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 4
  - Dependencies: E2-T6,E5-T3
  - Deliverable: validated IAM bindings, impersonation paths, and secret access evidence

- E5-T6 Enforce global campaign labels in provisioned modules and verify compliance
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 4
  - Dependencies: E1-T5,E5-T2
  - Deliverable: label compliance report

- E5-T7 Provision campaign runtime prerequisites and validate health endpoint
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 4
  - Dependencies: E5-T3,E5-T5,E5-T6
  - Deliverable: runtime prerequisite checklist, pinned image digest record, and healthy endpoint evidence

- E5-T8 Week 4 infrastructure gate review
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 4
  - Dependencies: E5-T1,E5-T2,E5-T3,E5-T4,E5-T5,E5-T6,E5-T7
  - Deliverable: signed Week 4 infrastructure gate report

## Epic E6 - Cloud Data Provisioning and Integration Bring-up

Objective:

- Materialize datasets, graph state, and mandatory integrations after the environment is live.

Success criteria:

- Data quality gates pass on provisioned resources.
- Mandatory integrations pass smoke tests.
- Agent scopes are frozen before core benchmark execution.

Tasks:

- E6-T1 Provision and ingest structured data into raw and curated BigQuery datasets
  - Status: Done
  - Priority: P0
  - Estimate: L
  - Week: 4-5
  - Dependencies: E3-T2,E5-T8
  - Deliverable: dataset provisioning evidence, load logs, and row count reconciliation

- E6-T2 Provision corpus buckets and ingest text corpus into GCS with metadata tags
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 4-5
  - Dependencies: E3-T3,E5-T8
  - Deliverable: bucket provisioning evidence and object inventory with source, date, and sensitivity metadata

- E6-T3 Provision Spanner graph structures and seed entities and edges for validation scenarios
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 4-5
  - Dependencies: E3-T4,E5-T8
  - Deliverable: graph provisioning evidence, seeding report, counts, and no-evidence scenario fixtures

- E6-T4 Execute data quality gates on provisioned resources
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 5
  - Dependencies: E3-T5,E6-T1,E6-T2,E6-T3
  - Deliverable: pass/fail scorecard with thresholds, including null and isolated-node checks

- E6-T5 Configure mandatory integrations (Slack, Calendar, Jira, GitHub)
  - Status: Done
  - Priority: P0
  - Estimate: L
  - Week: 5
  - Dependencies: E2-T4,E5-T8
  - Deliverable: integration configuration records

- E6-T6 Build and run connector smoke suite and fallback diagnostics
  - Status: Done
  - Priority: P1
  - Estimate: M
  - Week: 5
  - Dependencies: E2-T5,E6-T5
  - Deliverable: smoke test logs and failure taxonomy mapping

- E6-T7 Freeze agent permissions and connector config versions
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 5
  - Dependencies: E6-T4,E6-T6
  - Deliverable: baseline freeze manifest

- E6-T8 Week 5 readiness gate review
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 5
  - Dependencies: E6-T1,E6-T2,E6-T3,E6-T4,E6-T5,E6-T6,E6-T7
  - Deliverable: signed Week 5 readiness gate report

## Epic E7-prep - Benchmark Preparation Offline

Objective:

- Complete all offline preparation (runners, statistics, observability, cost tracking, report templates) so that GCP infrastructure access is deferred until the final launch window.

Success criteria:

- Benchmark runner architecture is complete and tested in dry-run mode.
- Statistical computation framework is ready to process benchmark results.
- Observability templates are pre-built and ready to deploy.
- Cost tracking and hard-stop enforcement logic is pre-built.
- Executive report templates are complete.
- All scenario definitions validated against agent code paths.

Tasks:

- E7-prep-T1 Design and implement benchmark scenario runner architecture
  - Status: Done
  - Priority: P0
  - Estimate: L
  - Week: 1-2 (2026-07-09 to 2026-07-22)
  - Dependencies: E4-T2,E6-T6
  - Deliverable: benchmark_runners.py with ScenarioRunner, BenchmarkOrchestrator classes; dry-run test passing

- E7-prep-T2 Build statistical analysis framework (KPI scoring, confidence intervals, effect sizes)
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 1-2
  - Dependencies: E4-T5
  - Deliverable: statistics_engine.py with KPIScoringEngine, ConfidenceIntervalComputer; unit tests passing

- E7-prep-T3 Pre-build observability infrastructure (logging, tracing, monitoring)
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 1-2
  - Dependencies: E5-T6
  - Deliverable: observability_templates.yaml with queries, trace spans, dashboard configs

- E7-prep-T4 Build cost tracking and hard-stop enforcement logic
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 1-2
  - Dependencies: E4-T6,E5-T4
  - Deliverable: cost_controller.py with CostLedger, HardStopPolicy; unit tests passing

- E7-prep-T5 Create executive report templates and visualization specs
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 1-2
  - Dependencies: E4-T7
  - Deliverable: report_template.md, visualization_specs.json, decision_matrix_template.xlsx

- E7-prep-T6 Validate benchmark scenarios against agent code paths
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 1-2
  - Dependencies: E4-T2,src/agents/
  - Deliverable: agent_path_validation_report.md with scenario-to-code mapping

- E7-prep-T7 Design failure taxonomy and rerun eligibility rules
  - Status: Done
  - Priority: P0
  - Estimate: M
  - Week: 1-2
  - Dependencies: E4-T5,E6-T6
  - Deliverable: failure_taxonomy.md and rerun_eligibility_rules.yaml

- E7-prep-T8 Pre-stage E7-exec launch checklists and automation scripts
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 1-2
  - Dependencies: E7-prep-T1 through E7-prep-T7
  - Deliverable: E7-exec-launch-checklist.md, deploy_observability.sh, launch_benchmarks.sh

- E7-prep-T9 Week 2 offline readiness gate review
  - Status: Done
  - Priority: P0
  - Estimate: S
  - Week: 2 (2026-07-22)
  - Dependencies: E7-prep-T1 through E7-prep-T8
  - Deliverable: signed Week 2 offline readiness gate report (all offline work complete, ready for same-day launch)

## Epic E7-exec - Same-Day Benchmark Launch and Execution

Objective:

- Validate GCP infrastructure readiness and immediately execute benchmark scenarios on 2026-07-23 (same day).

Success criteria:

- Infrastructure validation passes in <1 hour.
- Benchmark execution commences same day.
- All 400+ runs complete within TTL window (2026-07-27).
- Cost tracking stays within hard-stop limit ($260).

Tasks:

- E7-exec-T1 Validate GCP infrastructure health and freeze status (1-hour window)
  - Priority: P0
  - Estimate: S
  - Week: 3 (2026-07-23, 00:00-01:00 UTC)
  - Dependencies: E6-T8,E5-T8
  - Deliverable: infrastructure_validation_report.md (all systems green)

- E7-exec-T2 Deploy observability infrastructure (logging, tracing, monitoring)
  - Priority: P0
  - Estimate: S
  - Week: 3 (2026-07-23, 01:00-02:00 UTC)
  - Dependencies: E7-prep-T3
  - Deliverable: deployment confirmation, dashboard URLs live

- E7-exec-T3 Launch benchmark execution for all 12 scenarios (360+ mandatory runs)
  - Priority: P0
  - Estimate: L
  - Week: 3-4 (2026-07-23 through 2026-07-27)
  - Dependencies: E7-exec-T1,E7-exec-T2,E7-prep-T1
  - Deliverable: raw run logs, metrics ingestion, token tracking data

- E7-exec-T4 Monitor cost burn in real-time; trigger hard-stop if needed
  - Priority: P0
  - Estimate: M
  - Week: 3-4
  - Dependencies: E7-prep-T4,E7-exec-T3
  - Deliverable: cost control ledger, hard-stop decision log (if triggered)

- E7-exec-T5 Run locked baselines under identical constraints
  - Priority: P0
  - Estimate: M
  - Week: 3-4
  - Dependencies: E7-exec-T3
  - Deliverable: baseline comparison dataset

- E7-exec-T6 Classify failures by taxonomy and record rerun eligibility
  - Priority: P1
  - Estimate: M
  - Week: 3-4
  - Dependencies: E7-exec-T3,E7-exec-T5
  - Deliverable: failure taxonomy report and rerun eligibility log

- E7-exec-T7 Execute approved reruns (if any instability detected)
  - Priority: P1
  - Estimate: M
  - Week: 3-4
  - Dependencies: E7-exec-T6
  - Deliverable: rerun evidence and justification log

- E7-exec-T8 Execute extended scenarios (if budget allows)
  - Priority: P2
  - Estimate: M
  - Week: 4
  - Dependencies: E7-exec-T4,E7-exec-T5
  - Deliverable: extended scope result pack

- E7-exec-T9 Week 3 execution gate review
  - Priority: P0
  - Estimate: S
  - Week: 4 (2026-07-27, pre-TTL)
  - Dependencies: E7-exec-T3,E7-exec-T5,E7-exec-T6,E7-exec-T7
  - Deliverable: signed Week 3 execution gate report

## Epic E8 - Post-Execution Analysis, Decision, and Controlled Closure

Objective:

- Consolidate benchmark results, produce decision package, and safely close campaign resources on schedule (2026-07-27).

Success criteria:

- Statistical analysis complete and confidence intervals computed.
- Decision matrix passed against acceptance criteria.
- All campaign resources deleted before TTL expiration.
- Zero residual GCP resources confirmed.

Tasks:

- E8-T1 Compute confidence intervals and effect-size analysis
  - Priority: P0
  - Estimate: M
  - Week: 4 (2026-07-27, post-E7-exec)
  - Dependencies: E7-exec-T5,E7-exec-T7
  - Deliverable: statistical_appendix.md with KPI, grounding, failure-pattern analysis

- E8-T2 Build pass/fail matrix against acceptance criteria
  - Priority: P0
  - Estimate: S
  - Week: 4
  - Dependencies: E8-T1
  - Deliverable: decision_matrix.xlsx for approval meeting

- E8-T3 Publish final validation report, cost/risk package, and go/no-go recommendation
  - Priority: P0
  - Estimate: S
  - Week: 4
  - Dependencies: E8-T2,E7-exec-T8
  - Deliverable: final_benchmark_report.md with recommendations and residual risk statement

- E8-T4 Prepare teardown checklist and protected-resource denylist
  - Priority: P0
  - Estimate: S
  - Week: 4
  - Dependencies: E5-T2
  - Deliverable: teardown_checklist.md with protected resources

- E8-T5 Execute phase-1 terraform destroy in campaign workspace
  - Priority: P0
  - Estimate: S
  - Week: 4 (2026-07-27, pre-TTL midnight UTC)
  - Dependencies: E8-T4
  - Deliverable: destroy execution log with manual approval record

- E8-T6 Execute phase-2 residual scan (inventory + labels)
  - Priority: P0
  - Estimate: S
  - Week: 4
  - Dependencies: E8-T5
  - Deliverable: residual_scan_report.md (target: zero billable resources)

- E8-T7 Perform delayed billing verification (24h post-destroy)
  - Priority: P0
  - Estimate: S
  - Week: 4-5 (2026-07-28)
  - Dependencies: E8-T6
  - Deliverable: billing_verification_report.md (confirm no billable resources remain)

- E8-T8 Publish final closure artifact package and campaign retrospective
  - Priority: P0
  - Estimate: S
  - Week: 4-5
  - Dependencies: E8-T3,E8-T7
  - Deliverable: closure_package.md with all artifacts, learnings, and post-campaign recommendations