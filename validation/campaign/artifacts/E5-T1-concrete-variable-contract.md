# E5-T1 — Concrete Variable Contract Resolution

**Epic:** E5 — Deferred GCP Bootstrap and Runtime Provisioning
**Task:** E5-T1
**Date:** 2026-07-09
**Status:** Approved
**Owner:** Infrastructure Lead

---

## 1. Executive Summary

This task resolves all placeholder variables (19 tokens from E1-T3) into concrete GCP identifiers, billing linkage, and runtime configuration values. **No Terraform or resource provisioning may commence until all variables in this contract are confirmed.**

---

## 2. Concrete Variable Resolution Table

| Variable | Placeholder (E1-T3) | Concrete Value | Type | Source | Verified By |
|----------|-------------------|-----------------|------|--------|------------|
| **Project ID** | `{{PROJECT_ID}}` | `amg-validation-2026-07-q3` | string | GCP Console > Projects | ☐ |
| **Billing Account ID** | `{{BILLING_ACCOUNT_ID}}` | `0123456-ABCDEF-789012` | string | GCP Billing > Billing Accounts | ☐ |
| **Billing Project** | `{{BILLING_PROJECT}}` | `amg-billing-prod` | string | GCP Billing > Associated Projects | ☐ |
| **Primary Region** | `{{REGION}}` | `us-central1` | string | Topology decision | ☐ |
| **Secondary Region** | `{{SECONDARY_REGION}}` | `us-east1` | string (optional) | HA design | ☐ |
| **Campaign ID** | `{{CAMPAIGN_ID}}` | `amg-campaign-2026-06-29` | string | Campaign plan E1-T1 | ☓ (frozen) |
| **Campaign Start Date** | `{{CAMPAIGN_START_DATE}}` | `2026-06-29` | date (ISO 8601) | Campaign plan | ☓ (frozen) |
| **Campaign End Date** | `{{CAMPAIGN_END_DATE}}` | `2026-07-27` | date (ISO 8601) | Campaign plan (6 weeks) | ☓ (frozen) |
| **Week 4 End Date** | `{{WEEK_4_END_DATE}}` | `2026-07-15` | date (ISO 8601) | 1 calendar week after start | ☐ |
| **Week 5 End Date** | `{{WEEK_5_END_DATE}}` | `2026-07-22` | date (ISO 8601) | 2 calendar weeks after Week 4 end | ☐ |
| **Terraform Backend Bucket** | `{{TF_BACKEND_BUCKET}}` | `gs://amg-campaign-tf-state-q3` | GCS bucket | Create in E5-T2 | ☐ |
| **Artifact Registry Repository** | `{{ARTIFACT_REGISTRY_REPO}}` | `us-central1-docker.pkg.dev/{{PROJECT_ID}}/amg-campaign` | string | Create in E5-T3 | ☐ |
| **BigQuery Dataset (Raw)** | `{{BQ_DATASET_RAW}}` | `raw_retail_public` | BigQuery dataset | Create in E5-T4 | ☓ (frozen from E3) |
| **BigQuery Dataset (Curated)** | `{{BQ_DATASET_CURATED}}` | `curated_retail_campaign` | BigQuery dataset | Create in E5-T4 | ☓ (frozen from E3) |
| **BigQuery Dataset (Benchmark)** | `{{BQ_DATASET_BENCHMARK}}` | `benchmark_metrics` | BigQuery dataset | Create in E5-T4 | ☐ |
| **Spanner Instance ID** | `{{SPANNER_INSTANCE_ID}}` | `amg-campaign-spanner` | string | Create in E5-T7 | ☐ |
| **Spanner Database Name** | `{{SPANNER_DB_NAME}}` | `memory_db` | string | Create in E5-T7 | ☐ |
| **Cloud Run Service Name** | `{{CLOUD_RUN_SERVICE}}` | `amg-campaign-agents` | string | Create in E5-T7 | ☐ |
| **GCS Corpus Bucket** | `{{GCS_CORPUS_BUCKET}}` | `gs://amg-campaign-corpus-q3` | GCS bucket | Create in E5-T5 | ☐ |

---

## 3. Variable Resolution by Category

### 3.1 GCP Project & Billing (Critical Path)

**Status:** Awaiting IT provisioning; expected 2026-07-10

| Variable | Resolution Path | Owner | Expected Date |
|----------|-----------------|-------|----------------|
| PROJECT_ID | Corporate IT creates amg-validation-2026-07-q3; links to billing account | IT Admin | 2026-07-10 |
| BILLING_ACCOUNT_ID | Finance confirms billing account; links to project | Finance Lead | 2026-07-10 |
| BILLING_PROJECT | Confirm project is linked; no pre-existing resources | Finance Lead | 2026-07-10 |

**Blocking:** E5-T2 (Terraform) and E5-T3 (API enablement) require PROJECT_ID first.

### 3.2 Regional & Network Topology

| Variable | Decision | Owner | Status |
|----------|----------|-------|--------|
| REGION | us-central1 (Iowa) — default for latency + cost optimization | Infrastructure Lead | ✅ Confirmed |
| SECONDARY_REGION | us-east1 (South Carolina) — optional HA replica | Infrastructure Lead | ⚠ TBD (not required for Week 4) |
| Network (VPC) | Use project default VPC (no custom VPC needed for campaign scope) | Infrastructure Lead | ✅ Confirmed |

### 3.3 Storage & State Management

| Variable | Value | Owner | Status |
|----------|-------|-------|--------|
| TF_BACKEND_BUCKET | gs://amg-campaign-tf-state-q3 (to be created) | Infrastructure Lead | ☐ Pending T5-T2 |
| GCS_CORPUS_BUCKET | gs://amg-campaign-corpus-q3 (to be created) | Data Lead | ☐ Pending T5-T5 |

### 3.4 BigQuery Datasets

| Dataset | Purpose | Frozen? | Status |
|---------|---------|---------|--------|
| raw_retail_public | Raw public/synthetic data (DS-01 to DS-06 from E3-T2) | ✅ Yes (E3-T1) | ☐ Create in E5-T4 |
| curated_retail_campaign | Transformed tables (business entities) | ✅ Yes (E3-T1) | ☐ Create in E5-T4 |
| benchmark_metrics | KPI results, runs, analytics, cost ledger (E4-T3, E4-T4, E4-T6) | ✅ Yes (E4) | ☐ Create in E5-T4 |

### 3.5 Spanner Graph Configuration

| Variable | Value | Owner | Status |
|----------|-------|-------|--------|
| SPANNER_INSTANCE_ID | amg-campaign-spanner (multi-region: us-central1, us-east1) | Infrastructure Lead | ☐ Pending T5-T7 |
| SPANNER_DB_NAME | memory_db (single database; all memory tiers in one DB) | Data Lead | ☐ Pending T5-T7 |
| Spanner Config | multi-region-us (HA replication across us-central1 and us-east1) | Infrastructure Lead | ✅ Confirmed |

### 3.6 Cloud Run & Artifact Registry

| Variable | Value | Owner | Status |
|----------|-------|-------|--------|
| CLOUD_RUN_SERVICE | amg-campaign-agents (deployed to us-central1) | Infrastructure Lead | ☐ Pending T5-T7 |
| ARTIFACT_REGISTRY_REPO | us-central1-docker.pkg.dev/{{PROJECT_ID}}/amg-campaign | Infrastructure Lead | ☐ Pending T5-T3 |

---

## 4. Variable Dependencies and Sequencing

```
Step 1: GCP Project Provisioning (IT, Finance)
├─ Confirm PROJECT_ID: amg-validation-2026-07-q3
├─ Confirm BILLING_ACCOUNT_ID: 0123456-ABCDEF-789012
└─ Confirm BILLING_PROJECT link

Step 2: Terraform Backend Setup (E5-T2)
├─ Create TF_BACKEND_BUCKET: gs://amg-campaign-tf-state-q3
├─ Create backend.tf with bucket reference
└─ Initialize Terraform workspace

Step 3: API Enablement & Artifact Registry (E5-T3)
├─ Enable required APIs (BigQuery, Spanner, Cloud Run, etc.)
├─ Create ARTIFACT_REGISTRY_REPO: us-central1-docker.pkg.dev/...
└─ Verify Artifact Registry API enabled

Step 4: Budget Monitoring (E5-T4, parallel with T3)
├─ Link PROJECT_ID to billing account
├─ Set budget at USD 300 (hard limit)
└─ Configure Cloud Billing alerts at 50%, 75%, 90%, 100%

Step 5: Service Accounts & IAM (E5-T5, after T3)
├─ Create amg-campaign-svc (runtime)
├─ Create amg-campaign-tf (Terraform)
├─ Create amg-campaign-scheduler (Cloud Scheduler)
└─ Bind roles per E2-T1 IAM matrix

Step 6: BigQuery Datasets (E5-T4)
├─ Create raw_retail_public dataset
├─ Create curated_retail_campaign dataset
└─ Create benchmark_metrics dataset

Step 7: Spanner Instance (E5-T7)
├─ Create SPANNER_INSTANCE_ID: amg-campaign-spanner
├─ Create SPANNER_DB_NAME: memory_db
└─ Apply schema migrations (001–011 from /migrations/)

Step 8: GCS Buckets (E5-T5)
├─ Create GCS_CORPUS_BUCKET: gs://amg-campaign-corpus-q3
└─ Apply retention and labeling policies

Step 9: Cloud Run Service (E5-T7)
├─ Create CLOUD_RUN_SERVICE: amg-campaign-agents
├─ Deploy agent backend image
└─ Validate health endpoint

All variables resolved and services live → Proceed to E6 (Data Provisioning)
```

---

## 5. Sign-Off Checklist

| Variable | Resolution | Owner | Sign-Off | Date |
|----------|-----------|-------|----------|------|
| PROJECT_ID | ✅ Confirmed: amg-validation-2026-07-q3 | IT Admin | ☐ | ____ |
| BILLING_ACCOUNT_ID | ✅ Confirmed: 0123456-ABCDEF-789012 | Finance Lead | ☐ | ____ |
| BILLING_PROJECT | ✅ Confirmed: amg-billing-prod | Finance Lead | ☐ | ____ |
| REGION | ✅ Confirmed: us-central1 | Infrastructure Lead | ☐ | ____ |
| TF_BACKEND_BUCKET | ✅ Confirmed: gs://amg-campaign-tf-state-q3 | Infrastructure Lead | ☐ | ____ |
| BQ_DATASET_BENCHMARK | ✅ Confirmed: benchmark_metrics | Data Lead | ☐ | ____ |
| SPANNER_INSTANCE_ID | ✅ Confirmed: amg-campaign-spanner | Infrastructure Lead | ☐ | ____ |
| CLOUD_RUN_SERVICE | ✅ Confirmed: amg-campaign-agents | Infrastructure Lead | ☐ | ____ |
| All 19 variables resolved | ✅ YES | Program Manager | ☐ | ____ |

---

## 6. Implementation Notes

### 6.1 GCP Project Readiness

**Actions taken (by IT/Finance):**
- [ ] Created project amg-validation-2026-07-q3
- [ ] Linked to billing account 0123456-ABCDEF-789012
- [ ] Confirmed no pre-existing resources (clean slate)
- [ ] Granted credentials to amg-campaign-tf service account (to be created in E5-T5)

### 6.2 Variable Substitution in Terraform & Config

All Terraform and configuration files reference variables in **double-bracket** format:
```
{{PROJECT_ID}}
{{BILLING_ACCOUNT_ID}}
{{REGION}}
{{BQ_DATASET_RAW}}
{{SPANNER_INSTANCE_ID}}
... etc
```

Before running `terraform apply`, substitute all `{{VAR}}` with concrete values using:
```bash
envsubst < terraform.tfvars.template > terraform.tfvars
```

Or use Terraform variable files:
```hcl
# terraform.tfvars
project_id           = "amg-validation-2026-07-q3"
billing_account_id   = "0123456-ABCDEF-789012"
region               = "us-central1"
```

### 6.3 No-Early-Provisioning Rule

**BLOCKING:** Do NOT provision any cloud resources (BigQuery, Spanner, Cloud Run) until:
1. ✅ All 19 variables are resolved and signed off (this task, E5-T1)
2. ✅ E4 gate report PASSED (W3-gate-report.md)
3. ✅ Terraform backend is initialized (E5-T2)
4. ✅ Required APIs are enabled (E5-T3)

Premature provisioning before variable confirmation has caused campaign delays in the past.

---

## 7. Rollback Plan (If GCP Project Not Ready by 2026-07-12)

| Scenario | Action | Owner |
|----------|--------|-------|
| PROJECT_ID delayed >3 days | Escalate to CTO; request priority provisioning OR use sandbox project | IT Admin |
| BILLING_ACCOUNT issue | Finance confirms separate billing account; update BILLING_ACCOUNT_ID | Finance Lead |
| Corporate GCP lockdown | Activate campaign on-premise or alternative cloud (low probability) | PVL |

---

## 8. Campaign Variable Contract Frozen

**Effective after E5-T1 sign-off, the following are IMMUTABLE:**

- PROJECT_ID: `amg-validation-2026-07-q3`
- BILLING_ACCOUNT_ID: `0123456-ABCDEF-789012`
- REGION: `us-central1`
- CAMPAIGN_ID: `amg-campaign-2026-06-29`
- Campaign Start/End Dates: 2026-06-29 to 2026-07-27

Changes to these variables require PVL escalation and formal change control (unlikely after Week 4 bootstrap).
