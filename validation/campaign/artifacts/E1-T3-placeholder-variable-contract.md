# E1-T3 — Placeholder Variable Contract

**Epic:** E1 — Campaign Framing and Offline Readiness
**Task:** E1-T3
**Date:** 2026-07-08
**Status:** Active

---

## Purpose

This document defines the canonical set of placeholder variables used across all offline design artifacts (Epics E1–E4). Any artifact referencing a GCP-specific or campaign-specific identifier must use the placeholder token exactly as defined here.

---

## Placeholder Token Registry

| Token | Description | Expected Source | Expected By | Constraint |
|-------|-------------|----------------|-------------|-----------|
| `{{PROJECT_ID}}` | GCP project identifier for the campaign | Corporate IT | End of Week 3 | Must be a dedicated campaign project; not shared with production |
| `{{BILLING_ACCOUNT_ID}}` | GCP billing account linked to `{{PROJECT_ID}}` | Corporate IT | End of Week 3 | Must support budget alerts via Budgets API |
| `{{REGION}}` | Single GCP region for all campaign resources | Platform Engineer + PVL decision | Week 4 (E5-T1) | Exactly one region; candidate: `us-central1` |
| `{{CAMPAIGN_START_DATE}}` | ISO 8601 date when campaign begins (Week 1 Day 1) | PVL | On campaign kickoff | Format: `YYYY-MM-DD` |
| `{{CAMPAIGN_PLANNED_END_DATE}}` | ISO 8601 date for planned Week 6 end | PVL | On campaign kickoff | Must be `{{CAMPAIGN_START_DATE}}` + 42 days |
| `{{CAMPAIGN_HARD_STOP_DATE}}` | Latest permissible end date regardless of completion | PVL + PM | On campaign kickoff | Must be <= `{{CAMPAIGN_PLANNED_END_DATE}}` + 7 days |
| `{{TERRAFORM_BACKEND_BUCKET}}` | GCS bucket name for Terraform remote state | Platform Engineer | Week 4 (E5-T2) | Naming convention: `amg-campaign-tfstate-{{PROJECT_ID}}` |
| `{{ARTIFACT_REGISTRY_REPO}}` | Artifact Registry repository path for campaign images | Platform Engineer | Week 4 (E5-T3) | Naming convention: `{{REGION}}-docker.pkg.dev/{{PROJECT_ID}}/amg-campaign` |
| `{{CONTAINER_IMAGE_DIGEST}}` | Pinned `sha256:` digest for the AMG service image | Platform Engineer | Week 4 (E5-T7) | Must be pinned; floating tags (`:latest`) are not allowed |
| `{{SPANNER_INSTANCE_ID}}` | Cloud Spanner instance ID | Platform Engineer | Week 4 (E5-T7) | Naming convention: `amg-campaign-spanner` |
| `{{SPANNER_DATABASE_ID}}` | Cloud Spanner database ID | Platform Engineer | Week 4 (E5-T7) | Naming convention: `amg-campaign-db` |
| `{{BQ_DATASET_RAW}}` | BigQuery raw retail dataset ID | Platform Engineer | Week 4 (E5-T7) | Naming convention: `raw_retail_public` |
| `{{BQ_DATASET_CURATED}}` | BigQuery curated campaign dataset ID | Platform Engineer | Week 4 (E5-T7) | Naming convention: `curated_retail_campaign` |
| `{{BQ_DATASET_METRICS}}` | BigQuery benchmark metrics dataset ID | Platform Engineer | Week 4 (E5-T7) | Naming convention: `benchmark_metrics` |
| `{{GCS_CORPUS_BUCKET}}` | GCS bucket for raw data and text corpus | Platform Engineer | Week 4 (E5-T7) | Naming convention: `amg-campaign-corpus-{{PROJECT_ID}}` |
| `{{GCS_REPORTS_BUCKET}}` | GCS bucket for reports and exports (optional) | Platform Engineer | Week 5 | Naming convention: `amg-campaign-reports-{{PROJECT_ID}}` |
| `{{CAMPAIGN_RUN_ID_PREFIX}}` | Prefix for all benchmark run IDs | ML Lead | Week 3 (E4-T3) | Format: `campaign-2026-{scenario_id}-{run_seq}` |
| `{{BUDGET_CAP_USD}}` | Total campaign budget cap in USD | PVL + PM | Pre-campaign | Fixed at `300` per campaign plan |
| `{{BUDGET_HARD_STOP_USD}}` | Extended scope hard-stop threshold in USD | PVL + PM | Pre-campaign | Fixed at `260` per campaign plan |

---

## Usage Rules

1. Every offline design document (E1–E4) that references a GCP value MUST use the token form.
2. Tokens are resolved only in Epic E5-T1 when concrete values are approved.
3. No Terraform variable file, backend config, or script may be checked in with a resolved `{{PROJECT_ID}}` or `{{BILLING_ACCOUNT_ID}}` before E5-T1 approval.
4. `{{REGION}}` may be set to the candidate value `us-central1` in working drafts but must be marked as `[DRAFT — PENDING E5-T1]`.
5. `{{BUDGET_CAP_USD}}` and `{{BUDGET_HARD_STOP_USD}}` are resolved as constants: `300` and `260` respectively.

---

## Token Resolution Procedure

When E5-T1 is executed:
1. Platform Engineer confirms each token value with the relevant source.
2. Values are recorded in `E1-T3-unresolved-input-register.md` under the `Resolved Value` column.
3. The unresolved-input register is updated to `Status = Resolved`.
4. Platform Engineer propagates resolved values to Terraform variable files.
5. PVL reviews and approves the complete resolved register before E5-T2 begins.
