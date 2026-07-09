# GCP Product Validation Campaign Plan

## 1) Purpose and Decision Scope

This document defines a decision-grade validation campaign for Agent Memory Graph on GCP, aligned with the current repository architecture, deployment model, and quality gates.

Primary objective:
- Validate end-to-end technical behavior and operational viability in GCP with public and synthetic enterprise-like retail data.

Decision objective:
- Produce an auditable go/no-go recommendation for limited production pilot readiness.

Campaign constraints:
- Duration: 6 weeks (setup, execution, analysis, closure).
- Budget cap: USD 300 total.
- Data policy: only public and synthetic data.
- Company model: retail and e-commerce.
- Infrastructure policy: Terraform-managed resources, with explicit exceptions for OAuth consent bootstrap and external connector app setup.
- Success gate: pass if all mandatory acceptance criteria in Section 13 are met.

## 2) Campaign Scope and Tiering Decisions

### 2.1 Mandatory scope (must pass)

- Memory-backed retrieval and synthesis through product runtime.
- Spanner memory operations and audit trace integrity.
- BigQuery ingestion and benchmark metrics storage.
- GCS text corpus retrieval path.
- Integrations: Slack, Google Calendar, Jira, GitHub.

### 2.2 Extended scope (nice to have, non-blocking)

- Integrations: Gmail, Drive, Confluence, GitLab.
- Additional optional agent archetypes.

### 2.3 Explicit assumptions

- PROJECT_ID is provided by corporate IT before end of Week 1.
- Campaign uses one region to reduce cost and control latency variance.
- Baseline comparisons are executed under the same task corpus, timeout policy, and retry policy as the product run.

## 3) Outcomes and Exit Artifacts

Required campaign outcomes:
- Evidence-based validation report for all mandatory product functions.
- Benchmark comparison against all baseline methods.
- Cost report with planned, actual, and forecasted totals.
- Security and governance compliance checklist results.
- Teardown evidence report proving no residual campaign resources.
- Reproducibility bundle (run manifests, seeds, model and prompt versions, configuration hashes).

## 4) Workstreams and Ownership

Workstreams:
- W1: GCP environment lifecycle and Terraform controls.
- W2: Data design, ingestion, and quality gates.
- W3: Agent definitions, permissions, and connector hardening.
- W4: Benchmark protocol and execution.
- W5: Observability and KPI analytics.
- W6: Cost governance and teardown automation.

Ownership model (RACI decision):
- Accountable: Product validation lead.
- Responsible per workstream: one named owner per workstream.
- Consulted: Security reviewer, MLE lead, platform engineer.
- Informed: Product manager and stakeholder steering group.

## 5) Timeline with Stage Gates (6 Weeks)

## Week 1: Setup and Access

Tasks:
- Receive PROJECT_ID and confirm billing account linkage.
- Configure Terraform backend and workspace strategy.
- Provision IAM service accounts, secrets, and runtime prerequisites.
- Enable required APIs.

Gate exit criteria:
- Terraform init, plan, and apply succeed in campaign workspace.
- Health endpoint returns healthy.
- Budget alerts and monitoring policies are active.

## Week 2: Data Foundation

Tasks:
- Provision and populate BigQuery datasets.
- Provision and populate GCS text corpus.
- Seed Spanner functional graph data.
- Run data quality validations.

Gate exit criteria:
- Data quality thresholds pass (Section 7.5).
- Referential integrity and graph connectivity checks pass.
- Data provenance and license records completed.

## Week 3: Agent and Integration Setup

Tasks:
- Freeze agent profiles and allowed tool scopes.
- Configure mandatory integrations.
- Run smoke scenarios per agent and integration.

Gate exit criteria:
- All mandatory integrations pass smoke tests.
- IAM and authorization-scope matrix validated.
- No critical authz or secret-handling findings open.

## Week 4: Core Benchmark Execution

Tasks:
- Run mandatory benchmark scenarios with controlled windows.
- Collect product and baseline metrics side by side.
- Log and classify failures by taxonomy.

Gate exit criteria:
- Minimum sample size reached for each mandatory scenario.
- Cost forecast to end-of-campaign remains <= USD 300.
- Re-run candidates identified only by statistical and reliability rules.

## Week 5: Extended Runs and Analysis

Tasks:
- Re-run unstable scenarios only when rerun criteria are met.
- Execute extended integration scenarios if budget permits.
- Consolidate KPI, groundedness, and failure-pattern analysis.

Gate exit criteria:
- Confidence intervals computed for core KPIs.
- Final pass/fail table prepared for approval meeting.

## Week 6: Report, Decision, and Closure

Tasks:
- Publish final report and go/no-go recommendation.
- Trigger controlled teardown workflow.
- Validate post-destroy residual resource scan and billing checks.

Gate exit criteria:
- All mandatory acceptance criteria are met.
- Teardown evidence accepted by platform owner.

## 6) GCP Management Plan

## 6.1 Inputs and Governance Contract

Required inputs:
- PROJECT_ID.
- BILLING_ACCOUNT_ID.
- REGION (fixed to one campaign region after Week 1 decision).
- Campaign end date and hard stop date.

Required labels on all campaign resources:
- campaign=validation-2026
- owner=product-team
- env=campaign
- ttl=6-weeks
- auto_delete=true

Governance decision:
- Labels are mandatory but are not the primary deletion selector. Primary selector is Terraform state and module inventory; labels are a verification filter.

## 6.2 Required APIs

Enable via Terraform:
- compute.googleapis.com
- run.googleapis.com
- spanner.googleapis.com
- bigquery.googleapis.com
- storage.googleapis.com
- cloudresourcemanager.googleapis.com
- iam.googleapis.com
- serviceusage.googleapis.com
- cloudbilling.googleapis.com
- monitoring.googleapis.com
- logging.googleapis.com
- cloudscheduler.googleapis.com
- secretmanager.googleapis.com
- artifactregistry.googleapis.com

## 6.3 Infrastructure to Create

Spanner:
- 1 campaign instance.
- 1 campaign database for memory graph validation.
- Processing units: minimum baseline, increase only during benchmark windows.

Cloud Run runtime:
- Service deployed from pinned image digest.
- Min and max instances fixed for campaign profile.
- Health checks, traces, and log metrics enabled.

BigQuery:
- raw_retail_public
- curated_retail_campaign
- benchmark_metrics

GCS:
- 1 bucket for raw and text corpus assets.
- 1 optional bucket for reports and exports.
- Lifecycle retention policy set at creation.

## 6.4 Population and Data Movement

- Infrastructure and identities provisioned by Terraform.
- Data ingestion executed by controlled scripts and logged to run manifest.
- Every load records source, version, checksum, and timestamp.

## 6.5 Cost and Safety Controls

Budget controls:
- Budget cap: USD 300.
- Alert thresholds: 50%, 75%, 90%, 100%.
- Daily burn-rate forecast with projected final cost.
- Hard stop trigger if forecast exceeds USD 260 before end of Week 4.

Runtime controls:
- Time-box benchmark windows.
- Cap max concurrency for non-critical runs.
- Restrict reruns to scenarios failing stability criteria.

## 6.6 Teardown Protocol (Two-Phase, Safe)

Phase 1: Controlled destroy
- Execute terraform destroy from the campaign workspace and state.
- Require one manual approval before destroy command execution.

Phase 2: Residual verification
- Query residual resources by Terraform inventory and by campaign labels.
- Verify zero residual billable resources.
- Validate billing export for delayed charges within a 24-hour follow-up check.

Safety rules:
- Never delete outside campaign workspace scope.
- Never use label-only deletion as primary mechanism.
- Preserve audit artifacts and final reports in designated retention location.

## 7) Dataset Design (Multi-Format, Retail and E-commerce)

## 7.1 Design Goals

- Simulate realistic enterprise workflows across sales, support, and operations.
- Stress memory retrieval, evidence grounding, and integration orchestration.
- Support graph traversal and evidence chaining.

## 7.2 Structured Data in BigQuery

Core domains:
- Customers, accounts, consent preferences.
- Products, pricing, hierarchy.
- Orders, items, payments, refunds.
- Inventory and fulfillment events.
- Support tickets and SLA metadata.
- Marketing interactions.
- Employee task and queue metadata.

Scale decision:
- Target 10-50 GB with representative skew and seasonality.

Provenance decision:
- Each source dataset must include license type, allowed use, and attribution record before ingestion.

## 7.3 Unstructured Data in GCS

Corpus types:
- Product manuals and policy text.
- Public or synthetic customer communications.
- SOP documents.
- Integration event narratives.

Quality decision:
- Every unstructured file includes metadata tags for source, date, and sensitivity class.

## 7.4 Functional Graph Data in Spanner

Example entities:
- Customer, Account, Product, Order, Ticket, Agent, Team, IntegrationEvent, Document.

Example edges:
- CUSTOMER_PLACED_ORDER
- ORDER_CONTAINS_PRODUCT
- CUSTOMER_OPENED_TICKET
- TICKET_REFERENCES_DOCUMENT
- AGENT_RESOLVED_TICKET
- INTEGRATION_EVENT_RELATED_TO_ORDER

Validation decision:
- Include explicit no-evidence scenarios to verify safe abstention behavior.

## 7.5 Data Quality and Integrity Gates

Pre-benchmark checks:
- Referential integrity across all key joins.
- Null threshold <= 1% on mandatory fields.
- Cardinality checks for keys and relationships.
- Distribution sanity checks for daily order and ticket rates.
- Graph connectivity with isolated-node threshold <= 5% for target entities.

Enforcement:
- Benchmark execution is blocked until all mandatory data quality checks pass.

## 8) Agent Set Definition and Security Boundaries

Mandatory archetypes:
- Employee Chatbot.
- Customer Chatbot.
- Task Assistant.
- Slack and Google Integration Manager.
- Calendar Manager.
- Code Assistant.

Optional archetypes:
- Incident Coordinator.
- Knowledge Curator.

For each mandatory agent define and freeze before Week 4:
- Allowed tools.
- Allowed memory tiers.
- Allowed data domains.
- Denied actions.
- Failure criteria and escalation path.

Security decision:
- Least privilege is mandatory. Broad wildcard permissions are not allowed.

## 9) Benchmark Battery and Evaluation Method

## 9.1 Objective

Measure correctness, groundedness, latency, reliability, and cost against standardized baselines.

## 9.2 Baselines (Locked)

For every scenario run all baselines under identical inputs and timeout policy:
- Manual human process.
- Script-based process without shared memory graph.
- Single-agent process without memory graph.
- Generic chatbot without enterprise integrations.

## 9.3 Mandatory KPI Definitions

Task success rate:
- Formula: successful_runs / total_runs.
- A run is successful only if required output, policy compliance, and completion time constraints are all met.

Groundedness score:
- Formula: supported_claims / total_material_claims.
- A material claim is supported only by verifiable evidence from approved sources in the run.

Latency:
- Report p50, p95, and p99 end-to-end latency.

Cost per task:
- Formula: total_campaign_cost_allocated_to_scenario / successful_runs.

Time saved vs baseline:
- Formula: median_baseline_duration - median_product_duration.

## 9.4 Additional KPIs

- Retry rate.
- Escalation rate.
- Integration completion rate.
- Evidence coverage ratio.
- Authorization denial rate.

## 9.5 Task Battery and Sample Size

Task battery:
- Maintain a benchmark catalog with scenario_id, input fixture, expected outcome, and pass rules.

Sample-size decision:
- Minimum 30 measured runs per mandatory scenario.
- Minimum 10 measured runs per extended scenario.

Execution protocol:
- Fixed random seed where applicable.
- Warm-up runs excluded from scoring.
- Measured runs timestamped with run_id and configuration hash.

## 9.6 Statistical Decision Rules

- Report 95% confidence intervals for success rate and groundedness.
- Do not claim improvement without positive effect size and non-overlapping confidence support.
- Reruns are allowed only for instability, infra failure, or insufficient sample size.

## 10) End-to-End Execution Flow (Repo-Aligned)

## Step 1: Prerequisites

- Install Terraform and gcloud CLI.
- Authenticate account and set active project.
- Configure remote Terraform state backend.
- Ensure Artifact Registry repository exists in target project.

## Step 2: Configure Variables

- Set PROJECT_ID, BILLING_ACCOUNT_ID, REGION, labels, and budget cap.
- Set campaign start, planned end, and hard stop timestamps.
- Pin container image digest and runtime configuration version.

## Step 3: Provision Infrastructure

- terraform init
- terraform plan
- terraform apply

Provision must include:
- IAM and service accounts.
- Secret Manager configuration.
- Cloud Run service and monitoring policies.
- Spanner instance and database.
- BigQuery and GCS campaign resources.
- Scheduler jobs required for campaign operations.

## Step 4: Data Population and Validation

- Execute ingestion workflows for BigQuery, GCS, and Spanner.
- Run data quality gates from Section 7.5.
- Publish data provenance register.

## Step 5: Configure Agents and Integrations

- Register agent profiles and authorization scopes.
- Configure mandatory integrations.
- Execute integration smoke tests and log results.

## Step 6: Benchmark Execution

- Run core benchmark windows first.
- Persist metrics, traces, and audit events.
- Monitor budget burn and reliability in real time.

## Step 7: Analyze and Decide

- Compute KPI summary with confidence intervals.
- Compare against locked thresholds.
- Produce go/no-go recommendation with residual risk statement.

## Step 8: Controlled Closure

- Run two-phase teardown protocol.
- Validate zero residual billable resources.
- Archive evidence package.

## 11) Cost Model and Control

Target:
- Total campaign spend <= USD 300.

## 11.1 Base scenario

- Spanner baseline and controlled bursts: USD 90-130.
- BigQuery storage and query jobs: USD 35-60.
- GCS storage and operations: USD 5-15.
- Cloud Run, Scheduler, Monitoring, Logging: USD 25-45.
- Integration and transfer overhead: USD 10-20.

Estimated base total:
- USD 165-270.

## 11.2 Peak scenario

- Spanner heavier windows: USD 130-170.
- BigQuery reruns: USD 55-85.
- GCS and operations: USD 15-25.
- Runtime and observability growth: USD 35-55.

Estimated peak total:
- USD 235-335.

Control decisions:
- Freeze extended scope if forecast > USD 260 by end of Week 4.
- Execute only mandatory reruns after Week 4.
- Teardown immediately after final decision approval.

## 12) Risk Register and Mitigation Plan

Cost overrun risk:
- Mitigation: daily forecast, hard stop threshold, strict rerun policy.

Methodology risk (invalid conclusions):
- Mitigation: fixed KPI formulas, sample-size minimums, confidence intervals.

Integration flakiness risk:
- Mitigation: smoke tests, retry policy, connector-specific fallback diagnostics.

Security misconfiguration risk:
- Mitigation: least-privilege matrix, secret scans, authz denial monitoring.

Teardown safety risk:
- Mitigation: two-phase destroy, workspace-bounded deletion, post-billing check.

Data licensing risk:
- Mitigation: mandatory provenance and usage-right validation before ingestion.

## 13) Acceptance Criteria (Mandatory)

Campaign passes only if all conditions are true:
- Task success rate >= 85% with 95% confidence interval lower bound >= 80%.
- Groundedness >= 0.90 with 95% confidence interval lower bound >= 0.85.
- Total cost <= USD 300.
- All mandatory agent archetypes validated.
- All mandatory integrations validated.
- No unresolved critical security findings.
- Teardown evidence confirms zero residual campaign resources.

## 14) Required Deliverables

- Validation runbook (step by step).
- Benchmark catalog and scoring rubric.
- Final benchmark report with statistical appendix.
- Risk and mitigation matrix with owner and status.
- Cost report (planned vs actual vs forecast).
- Security and compliance checklist report.
- Teardown evidence report.
- Reproducibility bundle.

## 15) Immediate Next Actions

- Receive PROJECT_ID from IT.
- Freeze Terraform variable contract and campaign workspace naming.
- Create benchmark catalog with scenario IDs and sample-size plan.
- Approve mandatory vs extended integration scope.
- Implement and validate two-phase teardown workflow.
- Start Week 1 provisioning tasks.
