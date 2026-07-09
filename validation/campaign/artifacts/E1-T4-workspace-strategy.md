# E1-T4 — Workspace Strategy and Naming Convention

**Epic:** E1 — Campaign Framing and Offline Readiness
**Task:** E1-T4
**Date:** 2026-07-08
**Status:** Approved

---

## 1. Workspace Strategy

### 1.1 Terraform Workspace Model

The campaign uses a **single dedicated Terraform workspace** named `campaign-validation`.

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Workspace isolation | Dedicated workspace per campaign | Prevents state pollution with production or staging workspaces |
| State backend | GCS remote backend | Supports team access, locking, and versioning |
| Workspace naming | `campaign-validation` | Unique, campaign-scoped, maps to label `env=campaign` |
| Destroy scope | Workspace-scoped only | Phase-1 `terraform destroy` is bounded to campaign workspace state |
| State retention | Retained post-destroy for 90 days | Required for audit evidence under E8-T8 |

### 1.2 Workspace Directory Layout

```
infrastructure/
└── terraform/
    └── campaign/
        ├── backend.hcl           ← from E1-T4-backend-config-template.md (generated at E5-T2)
        ├── main.tf               ← root module
        ├── variables.tf          ← all input variables (tokens as defaults where applicable)
        ├── terraform.tfvars      ← resolved values (created at E5-T1; NOT checked in with secrets)
        ├── outputs.tf            ← campaign resource outputs
        ├── versions.tf           ← provider and Terraform version pins
        └── modules/
            ├── iam/              ← service accounts and bindings
            ├── spanner/          ← Spanner instance and database
            ├── bigquery/         ← datasets and tables
            ├── gcs/              ← corpus and reports buckets
            ├── cloudrun/         ← AMG service
            ├── scheduler/        ← Cloud Scheduler jobs
            ├── monitoring/       ← budget alerts and dashboards
            └── secretmanager/    ← secret definitions
```

### 1.3 Workspace Activation Flow

```
E5-T1 approve variable contract
    → E5-T2 create GCS backend bucket (gcloud, pre-Terraform)
    → E5-T2 terraform init -backend-config=backend.hcl
    → E5-T2 terraform workspace new campaign-validation
    → E5-T3 enable APIs
    → E5-T5 apply iam module
    → E5-T7 apply remaining modules
```

---

## 2. Naming Convention

### 2.1 GCP Resource Naming

Pattern: `amg-campaign-{resource-type}[-{qualifier}]`

| Resource Type | Name | Notes |
|--------------|------|-------|
| Spanner instance | `amg-campaign-spanner` | Fixed across environments |
| Spanner database | `amg-campaign-db` | |
| Cloud Run service | `amg-campaign-svc` | |
| GCS corpus bucket | `amg-campaign-corpus-{{PROJECT_ID}}` | Must be globally unique |
| GCS reports bucket | `amg-campaign-reports-{{PROJECT_ID}}` | |
| Terraform state bucket | `amg-campaign-tfstate-{{PROJECT_ID}}` | |
| Artifact Registry | `amg-campaign` | Under `{{REGION}}-docker.pkg.dev/{{PROJECT_ID}}/` |
| Service account (runtime) | `amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com` | |
| Service account (terraform) | `amg-campaign-tf@{{PROJECT_ID}}.iam.gserviceaccount.com` | |
| Secret (API key) | `amg-campaign-api-key` | |
| Secret (integration token prefix) | `amg-campaign-{integration}-token` | e.g. `amg-campaign-slack-token` |
| Budget alert | `amg-campaign-budget` | |
| Monitoring dashboard | `amg-campaign-dashboard` | |
| BigQuery dataset (raw) | `raw_retail_public` | BigQuery uses underscores, no prefix |
| BigQuery dataset (curated) | `curated_retail_campaign` | |
| BigQuery dataset (metrics) | `benchmark_metrics` | |
| Cloud Scheduler jobs | `amg-campaign-{job-type}` | e.g. `amg-campaign-daily-burn` |

### 2.2 Artifact File Naming (Campaign Worktree)

Pattern: `E{epic}-T{task}-{descriptor-kebab-case}.md`

| Type | Pattern | Example |
|------|---------|---------|
| Task artifact | `E{e}-T{t}-{descriptor}.md` | `E2-T1-iam-matrix.md` |
| Gate report | `gates/W{week}-{scope}-gate-report.md` | `gates/W1-gate-report.md` |
| Run manifest | `run-manifests/{run_id}-manifest.json` | `run-manifests/campaign-2026-EMC-001-manifest.json` |

### 2.3 Benchmark Run ID Schema

Pattern: `campaign-2026-{SCENARIO_ID}-{RUN_SEQ:03d}`

| Component | Description | Example |
|-----------|-------------|---------|
| `campaign-2026` | Campaign year prefix | Fixed |
| `{SCENARIO_ID}` | Scenario identifier from benchmark catalog | `EMC` (Employee Memory Chatbot) |
| `{RUN_SEQ:03d}` | Zero-padded sequential run number | `001`, `002`, …, `030` |
| Full example | | `campaign-2026-EMC-001` |

---

## 3. Environment Labels (Reference)

See `E1-T5-label-policy.md` for the full label policy. Quick reference:

| Key | Value |
|-----|-------|
| `campaign` | `validation-2026` |
| `owner` | `product-team` |
| `env` | `campaign` |
| `ttl` | `6-weeks` |
| `auto_delete` | `true` |
