# E1-T6 — Offline Validation Runbook

**Epic:** E1 — Campaign Framing and Offline Readiness
**Task:** E1-T6
**Date:** 2026-07-08
**Status:** Active (Weeks 1–3)

---

## Purpose

This runbook defines how to execute the offline phase of the campaign (Weeks 1–3) without any live GCP identifiers. Following this runbook allows all design, security, data, and protocol work to proceed in parallel with the corporate IT provisioning queue.

---

## Preconditions

Before starting the offline phase:
- [ ] Backlog is approved and in the campaign-validation worktree
- [ ] Sequencing decision note (E1-T1) is signed
- [ ] RACI matrix (E1-T2) identifies owners for every workstream
- [ ] All team members have access to the campaign-validation worktree

No GCP account, project, or billing access is required during Weeks 1–3.

---

## Week 1 Runbook — Epic E1

**Objective:** Freeze campaign governance, framing, and artifact model.

| Step | Action | Owner | Artifact | Verification |
|------|--------|-------|---------|-------------|
| 1.1 | Execute E1-T1: author and approve sequencing decision note | PVL | E1-T1-sequencing-decision-note.md | Approval signatures on artifact |
| 1.2 | Execute E1-T2: create artifact index, evidence register, RACI | PVL | E1-T2-*.md | All three artifacts created and reviewed |
| 1.3 | Execute E1-T3: draft placeholder variable contract and unresolved-input register | PE | E1-T3-*.md | All 19 tokens defined; budget constants resolved |
| 1.4 | Execute E1-T4: prepare backend config template and workspace strategy | PE | E1-T4-*.md | Backend template marked as draft; workspace strategy approved |
| 1.5 | Execute E1-T5: define label policy, naming convention, artifact folder structure | PE | E1-T5-label-policy.md | Label policy approved; folder structure in place |
| 1.6 | Execute E1-T6: publish this runbook; conduct W1 gate review | PVL | E1-T6-offline-runbook.md, gates/W1-gate-report.md | Gate report signed |

**Week 1 gate criteria:**
- All E1 tasks are Done in the backlog
- Evidence register shows 11 artifacts with Reviewed dates
- No E2–E8 task has started without its dependency being Done
- Placeholder variable contract contains all 19 tokens
- RACI matrix is approved by PVL and PE

---

## Week 2 Runbook — Epics E2 and E3

**Objective:** Freeze security design and data design; no cloud resources required.

### E2 Track — Security, Agent, and Integration Design

| Step | Action | Owner | Artifact |
|------|--------|-------|---------|
| 2.1 | Build IAM matrix by agent and integration | SR | E2-T1-iam-matrix.md |
| 2.2 | Define agent profiles, policy boundaries, allowed tools, denied actions | ML | E2-T2-agent-profile-catalog.md |
| 2.3 | Define secret inventory and access policy | SR | E2-T3-secret-inventory.md |
| 2.4 | Document integration prerequisites (Slack, Calendar, Jira, GitHub) | PE | E2-T4-integration-prerequisites.md |
| 2.5 | Prepare authz denial and privilege escalation smoke plan | SR | E2-T5-security-smoke-plan.md |
| 2.6 | Conduct W2 security design gate review | PVL + SR | gates/W2-security-gate-report.md |

### E3 Track — Data Design, Fixtures, and Provenance

| Step | Action | Owner | Artifact |
|------|--------|-------|---------|
| 3.1 | Define canonical schema map for retail domains | ML | E3-T1-schema-map.md |
| 3.2 | Select and register public and synthetic source datasets | ML | E3-T2-source-inventory.md |
| 3.3 | Prepare text corpus manifest and metadata tagging schema | ML | E3-T3-corpus-manifest.md |
| 3.4 | Define Spanner graph seed specification and no-evidence fixtures | ML | E3-T4-graph-seed-spec.md |
| 3.5 | Define data quality gates (referential, nulls, cardinality, connectivity) | ML | E3-T5-dq-scorecard-template.md |
| 3.6 | Complete provenance and licensing register | ML | E3-T6-provenance-register.md |
| 3.7 | Conduct W2 data design gate review | PVL + ML | gates/W2-data-gate-report.md |

**Week 2 gate criteria:**
- All E2 and E3 tasks are Done
- IAM matrix approved by SR and PVL
- Agent profiles frozen (no changes allowed after gate)
- Data schema map approved; source datasets registered with license evidence
- No data quality gate has a relaxed threshold without written justification

---

## Week 3 Runbook — Epic E4

**Objective:** Freeze benchmark protocol, observability contract, and cost-control model.

| Step | Action | Owner | Artifact |
|------|--------|-------|---------|
| 4.1 | Create benchmark catalog with scenario_id, pass rules, no-evidence cases | ML | E4-T1-benchmark-catalog.md |
| 4.2 | Define scoring rubric for task success and groundedness | ML | E4-T2-scoring-rubric.md |
| 4.3 | Implement run manifest schema (run_id, seed, versions, config hash) | PE | E4-T3-run-manifest-schema.md |
| 4.4 | Define observability event schema, trace plan, audit capture points | PE | E4-T4-observability-design.md |
| 4.5 | Validate KPI formulas and SQL templates | ML | E4-T5-kpi-sql-templates.md |
| 4.6 | Prepare cost ledger template, burn forecast method, hard-stop workflow | PVL | E4-T6-cost-control-ledger.md |
| 4.7 | Dry-run benchmark protocol on local/synthetic fixtures | ML | E4-T7-dry-run-report.md |
| 4.8 | Conduct W3 protocol gate review | PVL + ML | gates/W3-gate-report.md |

**Week 3 gate criteria:**
- All E4 tasks are Done
- Benchmark catalog has at minimum all mandatory scenario IDs from plan Section 8
- KPI SQL templates pass dry-run on synthetic data
- Sample-size plan confirmed (minimum 30 measured runs per mandatory scenario)
- Cost ledger has burn forecast method and hard-stop trigger at `{{BUDGET_HARD_STOP_USD}}` = 260 USD

---

## Cross-Cutting Offline Rules

These rules apply throughout Weeks 1–3:

| Rule | Description |
|------|-------------|
| RC0 | No task before E5 may depend on `{{PROJECT_ID}}`, `{{BILLING_ACCOUNT_ID}}`, `{{REGION}}`, or live cloud resources |
| Token discipline | Any GCP identifier referenced in an artifact must use the `{{TOKEN}}` form from E1-T3 |
| No scope additions | No new mandatory scenarios may be added to the benchmark catalog after the W2 data gate |
| Evidence first | A task is not Done until its artifact exists, has a Reviewed entry, and is updated in the evidence register |
| Gate sign-off | No epic's work begins after its gate is due without a signed gate report or an explicit deferral note from PVL |

---

## Transition to Cloud Phase (Week 4)

When all three offline gate reports (W1, W2, W3) are signed:

1. PE confirms `{{PROJECT_ID}}` and `{{BILLING_ACCOUNT_ID}}` receipt from corporate IT (E5-T1).
2. PVL approves the concrete variable contract.
3. PE executes E5-T2 (Terraform backend initialization).
4. Campaign proceeds through E5–E8 per the cloud-phase runbook (to be authored in E4 as part of E4-T4).

If GCP identifiers have not arrived by end of Week 3, PVL escalates to PM and SG and a timeline amendment is documented before Week 4 begins.
