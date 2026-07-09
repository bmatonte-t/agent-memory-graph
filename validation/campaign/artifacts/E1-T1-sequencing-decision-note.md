# E1-T1 — Sequencing Decision Note

**Epic:** E1 — Campaign Framing and Offline Readiness
**Task:** E1-T1
**Date:** 2026-07-08
**Status:** Approved
**Author:** Product Validation Lead

---

## 1. Problem Statement

The original campaign plan (GCP_Product_Validation_Campaign_Plan.md) placed cloud bootstrap, IAM provisioning, and runtime bring-up in Week 1. This assumed `PROJECT_ID` and `BILLING_ACCOUNT_ID` would be available before the campaign starts.

Corporate GCP identifiers and billing metadata are provided by corporate IT and are subject to procurement and administrative delays outside the campaign team's control. Treating Week 1 as the bootstrap window creates a hard dependency that, if missed, would cascade and compress every downstream week.

---

## 2. Decision

**Re-baseline the campaign into two sequential phases:**

| Phase | Weeks | Dependency | Gating condition |
|-------|-------|-----------|-----------------|
| Offline design and preparation | 1–3 | No live GCP inputs required | Design gate reviews for E1, E2, E3, E4 pass |
| Cloud-backed execution | 4–6 | Concrete GCP variables confirmed | E5-T1 variable contract approved |

This re-sequencing preserves campaign quality and allows all design, security, data, and benchmark protocol work to proceed in parallel with the IT provisioning queue.

---

## 3. Sequencing Rules (Binding)

### Rule RC0 — Deferred-Input Control

No task in Epic E1, E2, E3, or E4 may depend on concrete values for:
- `PROJECT_ID`
- `BILLING_ACCOUNT_ID`
- `REGION`
- Live cloud resources of any kind

All such tasks must use placeholder references defined in E1-T3.

### Rule RS1 — Offline Completeness

The campaign must be capable of progressing through the end of Week 3 with zero GCP identifiers resolved.

### Rule RS2 — Cloud Bootstrap Trigger

Cloud bootstrap (Epic E5) begins only after:
1. All four offline design gate reports (W1, W2, W3) are signed.
2. Concrete GCP variable contract (E5-T1) is approved.

### Rule RS3 — Design Freeze Before Provisioning

Agent profiles (E2-T2), data schema (E3-T1), and benchmark catalog (E4-T1) must be frozen before E5 tasks begin.

---

## 4. Revised Week-by-Week Mapping

| Week | Epics Active | Cloud Dependency |
|------|-------------|-----------------|
| 1 | E1 | None |
| 2 | E2, E3 | None |
| 3 | E4 | None |
| 4 | E5 | PROJECT_ID, BILLING_ACCOUNT_ID, REGION required |
| 5 | E6, E7 | All cloud resources active |
| 6 | E7 (tail), E8 | All cloud resources active |

---

## 5. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| GCP identifiers arrive after Week 3 | Medium | Rules RC0 and RS2 prevent premature dependencies; no timeline loss on design work |
| Design gates not signed in time | Low | Design work has no external blockers; owners accountable per RACI |
| Scope added during offline phase | Medium | Backlog freeze rule: no new mandatory scope added after W2 design gate |

---

## 6. Impact on Original Plan

The original document section "Week 1: Setup and Access" is superseded for planning purposes. Those tasks map directly to **Epic E5** (Weeks 4) in the revised backlog. No scope has been removed — only the sequencing of cloud-dependent tasks has shifted.

---

## 7. Approval

- [ ] Product Validation Lead: _______________________  Date: ____________
- [ ] Platform Engineer: _______________________  Date: ____________
- [ ] Stakeholder Group: Informed via kickoff communication
