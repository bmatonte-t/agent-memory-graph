# E1-T2 — Campaign Artifact Index

**Epic:** E1 — Campaign Framing and Offline Readiness
**Task:** E1-T2
**Date:** 2026-07-08
**Status:** Active (updated each sprint)

---

## Artifact Naming Convention

All campaign artifacts follow the pattern: `E{epic}-T{task}-{descriptor}.md`

Gate reports follow: `gates/W{week}-gate-report.md`

---

## Artifact Index

### Epic E1 — Campaign Framing and Offline Readiness

| ID | Artifact | File | Status | Owner | Reviewed |
|----|----------|------|--------|-------|---------|
| E1-T1 | Sequencing decision note + updated backlog | `E1-T1-sequencing-decision-note.md` | Done | Product Validation Lead | 2026-07-08 |
| E1-T2 | Artifact index (this file) | `E1-T2-artifact-index.md` | Done | Product Validation Lead | 2026-07-08 |
| E1-T2 | Evidence register | `E1-T2-evidence-register.md` | Done | Product Validation Lead | 2026-07-08 |
| E1-T2 | RACI matrix | `E1-T2-raci-matrix.md` | Done | Product Validation Lead | 2026-07-08 |
| E1-T3 | Placeholder variable contract | `E1-T3-placeholder-variable-contract.md` | Done | Platform Engineer | 2026-07-08 |
| E1-T3 | Unresolved-input register | `E1-T3-unresolved-input-register.md` | Done | Platform Engineer | 2026-07-08 |
| E1-T4 | Backend config template | `E1-T4-backend-config-template.md` | Done | Platform Engineer | 2026-07-08 |
| E1-T4 | Workspace strategy | `E1-T4-workspace-strategy.md` | Done | Platform Engineer | 2026-07-08 |
| E1-T5 | Label policy and naming standard | `E1-T5-label-policy.md` | Done | Platform Engineer | 2026-07-08 |
| E1-T6 | Offline validation runbook | `E1-T6-offline-runbook.md` | Done | Product Validation Lead | 2026-07-08 |
| E1-T6 | Week 1 design gate report | `gates/W1-gate-report.md` | Done | Product Validation Lead | 2026-07-08 |

### Epic E2 — Security, Agent, and Integration Design Readiness

| ID | Artifact | File | Status | Owner | Reviewed |
|----|----------|------|--------|-------|---------|
| E2-T1 | IAM matrix | `E2-T1-iam-matrix.md` | Todo | Security Reviewer | — |
| E2-T2 | Agent profile catalog | `E2-T2-agent-profile-catalog.md` | Todo | MLE Lead | — |
| E2-T3 | Secret inventory and access policy | `E2-T3-secret-inventory.md` | Todo | Security Reviewer | — |
| E2-T4 | Integration prerequisite catalog | `E2-T4-integration-prerequisites.md` | Todo | Platform Engineer | — |
| E2-T5 | Security smoke test plan | `E2-T5-security-smoke-plan.md` | Todo | Security Reviewer | — |
| E2-T6 | Week 2 security gate report | `gates/W2-security-gate-report.md` | Todo | Product Validation Lead | — |

### Epic E3 — Data Design, Fixtures, and Provenance Preparation

| ID | Artifact | File | Status | Owner | Reviewed |
|----|----------|------|--------|-------|---------|
| E3-T1 | Schema map | `E3-T1-schema-map.md` | Todo | MLE Lead | — |
| E3-T2 | Source dataset inventory | `E3-T2-source-inventory.md` | Todo | MLE Lead | — |
| E3-T3 | Text corpus manifest | `E3-T3-corpus-manifest.md` | Todo | MLE Lead | — |
| E3-T4 | Spanner graph seed specification | `E3-T4-graph-seed-spec.md` | Todo | MLE Lead | — |
| E3-T5 | Data quality scorecard template | `E3-T5-dq-scorecard-template.md` | Todo | MLE Lead | — |
| E3-T6 | Provenance and licensing register | `E3-T6-provenance-register.md` | Todo | MLE Lead | — |
| E3-T7 | Week 2 data design gate report | `gates/W2-data-gate-report.md` | Todo | Product Validation Lead | — |

### Epic E4 — Benchmark, Observability, and Cost Control Design

| ID | Artifact | File | Status | Owner | Reviewed |
|----|----------|------|--------|-------|---------|
| E4-T1 | Benchmark catalog v1 | `E4-T1-benchmark-catalog.md` | Todo | MLE Lead | — |
| E4-T2 | Scoring rubric and adjudication protocol | `E4-T2-scoring-rubric.md` | Todo | MLE Lead | — |
| E4-T3 | Run manifest schema | `E4-T3-run-manifest-schema.md` | Todo | Platform Engineer | — |
| E4-T4 | Observability and metrics design pack | `E4-T4-observability-design.md` | Todo | Platform Engineer | — |
| E4-T5 | KPI SQL templates | `E4-T5-kpi-sql-templates.md` | Todo | MLE Lead | — |
| E4-T6 | Cost control ledger template | `E4-T6-cost-control-ledger.md` | Todo | Product Validation Lead | — |
| E4-T7 | Dry-run report | `E4-T7-dry-run-report.md` | Todo | MLE Lead | — |
| E4-T8 | Week 3 protocol gate report | `gates/W3-gate-report.md` | Todo | Product Validation Lead | — |

### Epics E5–E8 — Cloud Execution Phase

Artifacts for E5–E8 are pre-registered below; files are created when their task becomes active.

| Epic | Artifact | Status |
|------|----------|--------|
| E5-T1 | Concrete variable contract | Deferred to Week 4 |
| E5-T8 | Week 4 infrastructure gate report | Deferred to Week 4 |
| E6-T8 | Week 5 readiness gate report | Deferred to Week 5 |
| E7-T7 | Week 5 execution gate report | Deferred to Week 5 |
| E8-T8 | Final closure artifact package | Deferred to Week 6 |

---

## Artifact Storage Rules

1. All artifacts are stored under `.worktree/campaign-validation/artifacts/`.
2. Gate reports are stored under `.worktree/campaign-validation/artifacts/gates/`.
3. No artifact is accepted as evidence until it has a non-empty `Reviewed` date in this index.
4. Artifact file names must match this index exactly — no ad hoc naming.
