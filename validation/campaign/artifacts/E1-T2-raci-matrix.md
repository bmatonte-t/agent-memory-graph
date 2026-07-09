# E1-T2 — Campaign RACI Matrix

**Epic:** E1 — Campaign Framing and Offline Readiness
**Task:** E1-T2
**Date:** 2026-07-08
**Status:** Approved

---

## Roles

| Role | Description |
|------|-------------|
| **PVL** | Product Validation Lead — Accountable for overall campaign quality and go/no-go recommendation |
| **PE** | Platform Engineer — Owns GCP infrastructure, Terraform, CI/CD, and runtime provisioning |
| **ML** | MLE Lead — Owns data design, agent definitions, benchmark protocol, and KPI analysis |
| **SR** | Security Reviewer — Owns IAM design, secret handling, and authz validation |
| **PM** | Product Manager — Informed on milestones and gate outcomes; not in critical path |
| **SG** | Stakeholder Group — Informed at major gates only |

**R** = Responsible (does the work) | **A** = Accountable (final sign-off) | **C** = Consulted | **I** = Informed

---

## Workstream Ownership

| Workstream | Lead | Backup |
|-----------|------|--------|
| W1: GCP environment lifecycle and Terraform | PE | PVL |
| W2: Data design, ingestion, and quality gates | ML | PE |
| W3: Agent definitions, permissions, and connectors | ML | SR |
| W4: Benchmark protocol and execution | ML | PVL |
| W5: Observability and KPI analytics | PE | ML |
| W6: Cost governance and teardown automation | PE | PVL |

---

## RACI by Epic and Task

### Epic E1 — Campaign Framing and Offline Readiness

| Task | PVL | PE | ML | SR | PM | SG |
|------|-----|----|----|----|----|----|
| E1-T1 Re-baseline sequencing | A/R | C | C | I | I | I |
| E1-T2 Artifact model, evidence register, RACI | A/R | C | C | I | I | I |
| E1-T3 Placeholder variable contract | A | R | I | I | I | I |
| E1-T4 Backend/workspace strategy template | A | R | C | C | I | I |
| E1-T5 Label policy and naming convention | A | R | C | I | I | I |
| E1-T6 Offline runbook and W1 gate review | A/R | C | C | C | I | I |

### Epic E2 — Security, Agent, and Integration Design

| Task | PVL | PE | ML | SR | PM | SG |
|------|-----|----|----|----|----|----|
| E2-T1 IAM matrix | C | C | I | A/R | I | I |
| E2-T2 Agent profile catalog | C | C | A/R | C | I | I |
| E2-T3 Secret inventory and access policy | C | C | I | A/R | I | I |
| E2-T4 Integration prerequisite catalog | C | A/R | C | C | I | I |
| E2-T5 Security smoke plan | C | C | C | A/R | I | I |
| E2-T6 W2 security gate review | A | C | C | R | I | I |

### Epic E3 — Data Design, Fixtures, and Provenance

| Task | PVL | PE | ML | SR | PM | SG |
|------|-----|----|----|----|----|----|
| E3-T1 Schema map | C | I | A/R | I | I | I |
| E3-T2 Source dataset inventory | C | I | A/R | I | I | I |
| E3-T3 Text corpus manifest | C | I | A/R | I | I | I |
| E3-T4 Spanner graph seed spec | C | C | A/R | I | I | I |
| E3-T5 Data quality gates | C | C | A/R | I | I | I |
| E3-T6 Provenance and licensing register | C | I | A/R | I | I | I |
| E3-T7 W2 data design gate review | A | C | R | C | I | I |

### Epic E4 — Benchmark, Observability, and Cost Control Design

| Task | PVL | PE | ML | SR | PM | SG |
|------|-----|----|----|----|----|----|
| E4-T1 Benchmark catalog | C | I | A/R | I | C | I |
| E4-T2 Scoring rubric | A | I | A/R | I | C | I |
| E4-T3 Run manifest schema | C | A/R | C | I | I | I |
| E4-T4 Observability event schema | C | A/R | C | C | I | I |
| E4-T5 KPI SQL templates | C | C | A/R | I | I | I |
| E4-T6 Cost ledger template | A/R | C | I | I | I | I |
| E4-T7 Dry-run report | A | C | R | I | I | I |
| E4-T8 W3 protocol gate review | A | C | R | C | I | I |

### Epic E5 — Deferred GCP Bootstrap and Runtime Provisioning

| Task | PVL | PE | ML | SR | PM | SG |
|------|-----|----|----|----|----|----|
| E5-T1 Concrete variable contract | A | R | I | I | I | I |
| E5-T2 Terraform backend and workspace | C | A/R | I | I | I | I |
| E5-T3 Enable APIs and verify readiness | C | A/R | I | I | I | I |
| E5-T4 Budget alerts and burn monitoring | A | R | I | I | I | I |
| E5-T5 Service accounts, IAM, Secret Manager | C | C | I | A/R | I | I |
| E5-T6 Campaign label compliance | C | A/R | I | I | I | I |
| E5-T7 Runtime prerequisites and health | C | A/R | C | C | I | I |
| E5-T8 W4 infrastructure gate review | A | R | C | C | I | I |

### Epics E6–E8 (Cloud Execution Phase)

| Task Group | PVL | PE | ML | SR | PM | SG |
|-----------|-----|----|----|----|----|----|
| E6: Data provisioning and integration | C | A | R | C | I | I |
| E7: Core benchmark execution | A | C | R | C | C | I |
| E8: Analysis, decision, and closure | A/R | C | C | C | C | I |
| E8: Final teardown and residual scan | A | R | I | I | I | I |

---

## Escalation Path

| Level | Trigger | Escalation Target |
|-------|---------|-----------------|
| L1 | Task blocked > 1 day | Workstream lead resolves internally |
| L2 | Gate criteria at risk | PVL convenes emergency review |
| L3 | Budget > 75% before Week 4 | PVL + PM joint decision on scope reduction |
| L4 | Critical security finding | SR + PVL joint decision; benchmark blocked |
| L5 | Go/no-go disagreement | SG arbitrates |
