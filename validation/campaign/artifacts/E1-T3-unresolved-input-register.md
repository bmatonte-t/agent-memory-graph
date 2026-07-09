# E1-T3 — Unresolved-Input Register

**Epic:** E1 — Campaign Framing and Offline Readiness
**Task:** E1-T3
**Date:** 2026-07-08
**Status:** Active (updated as inputs are resolved)

---

## Purpose

Tracks every unresolved campaign input. Each row must be resolved and signed by its owner before any downstream task that depends on it can begin. See `E1-T3-placeholder-variable-contract.md` for token definitions.

---

## Register

| Token | Expected Value | Source | Blocking Tasks | Expected By | Owner | Status | Resolved Value | Resolved Date |
|-------|---------------|--------|---------------|-------------|-------|--------|---------------|--------------|
| `{{PROJECT_ID}}` | TBD | Corporate IT | E5-T1, E5-T2, E5-T3, E5-T5 | End of Week 3 | PE | Unresolved | — | — |
| `{{BILLING_ACCOUNT_ID}}` | TBD | Corporate IT | E5-T1, E5-T4 | End of Week 3 | PE | Unresolved | — | — |
| `{{REGION}}` | Candidate: `us-central1` | PE + PVL decision | E5-T2, E5-T7, all E6 | Week 4 (E5-T1) | PE | Pending decision | — | — |
| `{{CAMPAIGN_START_DATE}}` | TBD | PVL | E1-T6, all scheduling | Campaign kickoff | PVL | Unresolved | — | — |
| `{{CAMPAIGN_PLANNED_END_DATE}}` | `{{CAMPAIGN_START_DATE}}` + 42d | PVL | E8-T4 | Campaign kickoff | PVL | Unresolved | — | — |
| `{{CAMPAIGN_HARD_STOP_DATE}}` | `{{CAMPAIGN_PLANNED_END_DATE}}` + ≤7d | PVL + PM | E8-T4 | Campaign kickoff | PVL | Unresolved | — | — |
| `{{TERRAFORM_BACKEND_BUCKET}}` | `amg-campaign-tfstate-{{PROJECT_ID}}` | PE | E5-T2 | Week 4 (E5-T2) | PE | Blocked on PROJECT_ID | — | — |
| `{{ARTIFACT_REGISTRY_REPO}}` | `{{REGION}}-docker.pkg.dev/{{PROJECT_ID}}/amg-campaign` | PE | E5-T3, E5-T7 | Week 4 (E5-T3) | PE | Blocked on PROJECT_ID | — | — |
| `{{CONTAINER_IMAGE_DIGEST}}` | `sha256:<pinned>` | PE | E5-T7 | Week 4 (E5-T7) | PE | Unresolved | — | — |
| `{{SPANNER_INSTANCE_ID}}` | `amg-campaign-spanner` | PE | E5-T7, E6-T3 | Week 4 (E5-T7) | PE | Pre-named (pending apply) | — | — |
| `{{SPANNER_DATABASE_ID}}` | `amg-campaign-db` | PE | E5-T7, E6-T3 | Week 4 (E5-T7) | PE | Pre-named (pending apply) | — | — |
| `{{BQ_DATASET_RAW}}` | `raw_retail_public` | PE | E6-T1 | Week 4 (E5-T7) | PE | Pre-named (pending apply) | — | — |
| `{{BQ_DATASET_CURATED}}` | `curated_retail_campaign` | PE | E6-T1 | Week 4 (E5-T7) | PE | Pre-named (pending apply) | — | — |
| `{{BQ_DATASET_METRICS}}` | `benchmark_metrics` | PE | E7-T1 | Week 4 (E5-T7) | PE | Pre-named (pending apply) | — | — |
| `{{GCS_CORPUS_BUCKET}}` | `amg-campaign-corpus-{{PROJECT_ID}}` | PE | E6-T2 | Week 4 (E5-T7) | PE | Blocked on PROJECT_ID | — | — |
| `{{GCS_REPORTS_BUCKET}}` | `amg-campaign-reports-{{PROJECT_ID}}` | PE | E8-T3 | Week 5 | PE | Blocked on PROJECT_ID | — | — |
| `{{CAMPAIGN_RUN_ID_PREFIX}}` | `campaign-2026-{scenario_id}-{run_seq}` | ML | E4-T3, E7-T1 | Week 3 (E4-T3) | ML | Pending E4-T3 | — | — |
| `{{BUDGET_CAP_USD}}` | `300` | Campaign plan | E4-T6, E7-T3 | Pre-campaign | PVL | Resolved | `300` | 2026-07-08 |
| `{{BUDGET_HARD_STOP_USD}}` | `260` | Campaign plan | E4-T6, E7-T3 | Pre-campaign | PVL | Resolved | `260` | 2026-07-08 |

---

## Resolution Summary

| Status | Count |
|--------|-------|
| Resolved | 2 |
| Pre-named (pending apply) | 6 |
| Pending decision / task | 3 |
| Blocked on PROJECT_ID | 4 |
| Unresolved | 4 |
| **Total** | **19** |

---

## Escalation Rule

If `{{PROJECT_ID}}` and `{{BILLING_ACCOUNT_ID}}` are not received by the end of Week 3, PVL must escalate to PM and SG to negotiate a Week 4 extension for cloud bootstrap without altering the benchmark scope.
