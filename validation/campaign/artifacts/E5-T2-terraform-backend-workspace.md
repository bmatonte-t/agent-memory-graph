# E5-T2 — Terraform Backend and Campaign Workspace Strategy

**Epic:** E5 — Deferred GCP Bootstrap and Runtime Provisioning
**Task:** E5-T2
**Date:** 2026-07-09
**Status:** Approved
**Owner:** Infrastructure Lead

---

## 1. Objective

Initialize the Terraform backend infrastructure (remote state storage) and activate the campaign Terraform workspace. This **must complete before any cloud resources are provisioned**.

---

## 2. Terraform Backend Architecture

### 2.1 Backend Storage: Cloud Storage (GCS)

**Location:** `gs://amg-campaign-tf-state-q3`

```hcl
terraform {
  backend "gcs" {
    bucket  = "amg-campaign-tf-state-q3"
    prefix  = "amg-campaign-2026-06-29"
    encryption_key = "{{TF_ENCRYPTION_KEY}}"  # base64-encoded; created in E5-T5
  }
}
```

**Features:**
- Versioning enabled (recover previous states)
- Encryption at rest (GCS CMEK or server-side)
- Public access blocked
- Logging enabled (who accessed state, when)
- Lifecycle policy: delete old versions after 90 days (post-campaign cleanup)

### 2.2 GCS Bucket Creation

**Before running `terraform init`:**

```bash
# Create backend bucket
gsutil mb -p {{PROJECT_ID}} -c STANDARD -l {{REGION}} gs://amg-campaign-tf-state-q3

# Enable versioning
gsutil versioning set on gs://amg-campaign-tf-state-q3

# Block public access
gsutil uniformbucketlevelaccess set on gs://amg-campaign-tf-state-q3

# Set lifecycle policy (delete noncurrent versions after 30 days)
gsutil lifecycle set - gs://amg-campaign-tf-state-q3 <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"numNewerVersions": 5}
      }
    ]
  }
}
EOF

# Enable logging to Cloud Logging
gsutil logging set on -b gs://amg-campaign-audit-logs -o access_logs gs://amg-campaign-tf-state-q3
```

### 2.3 Backend Access Control

| Principal | Role | Justification |
|-----------|------|----------------|
| `amg-campaign-tf@{{PROJECT_ID}}.iam.gserviceaccount.com` | `roles/storage.admin` on backend bucket | Terraform SA reads/writes state |
| `{{TF_APPROVER_EMAIL}}` (human) | `roles/storage.objectViewer` | Review state before apply |
| Cloud Audit Logs | Auto-logged | All state access audited |

**Deny List:** No unauthenticated access; no cross-project access; no public URLs.

---

## 3. Terraform Workspace Structure

### 3.1 Directory Layout

```
infrastructure/terraform/
├── backend.tf                 # Backend config (versioned after init)
├── provider.tf                # Provider + version constraints
├── variables.tf               # Input variables (project_id, region, etc.)
├── terraform.tfvars           # Concrete values (created from template in E5-T1)
├── main.tf                    # Main resource definitions
├── locals.tf                  # Local values and computed values
├── outputs.tf                 # Output values (for other tools)
├── labels.tf                  # Common label definitions (from E1-T5)
├── budget.tf                  # Budget alert resources (E5-T4)
├── iam.tf                     # Service account and role bindings (E5-T5)
├── network.tf                 # VPC, networking (minimal for campaign)
├── bigquery.tf                # BigQuery datasets and tables
├── spanner.tf                 # Spanner instance and database
├── cloudrun.tf                # Cloud Run service
├── storage.tf                 # GCS buckets (corpus, audit logs)
├── secrets.tf                 # Secret Manager secrets (E5-T5)
├── scheduler.tf               # Cloud Scheduler jobs (E6/E7)
├── monitoring.tf              # Cloud Monitoring dashboards (E5-T4)
├── modules/                   # Reusable terraform modules
│   ├── bigquery/
│   ├── spanner/
│   ├── cloud_run/
│   ├── iam/
│   └── monitoring/
├── .gitignore                 # Exclude terraform.tfvars, .tfstate
└── terraform.tfvars.template  # Template with {{VAR}} placeholders
```

### 3.2 Version Pinning (Provider & Modules)

```hcl
terraform {
  required_version = ">= 1.6, < 2.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.20"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.20"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
```

### 3.3 Common Labels & Tags

```hcl
# labels.tf
locals {
  campaign_labels = {
    campaign      = "validation-2026"
    owner         = "product-team"
    env           = "campaign"
    ttl           = "6-weeks"
    auto_delete   = "true"
    created_by    = "terraform"
    created_at    = "2026-07-09"
  }
}
```

**Applied to all resources:** BigQuery datasets, Spanner instances, Cloud Run services, GCS buckets, VMs, etc.

---

## 4. Terraform Initialization Checklist

### 4.1 Pre-Init Validation

- [ ] PROJECT_ID resolved and signed off (E5-T1)
- [ ] GCS backend bucket created and versioning enabled
- [ ] IAM roles assigned to amg-campaign-tf service account
- [ ] `terraform.tfvars` created from template (with actual values, not placeholders)
- [ ] `.gitignore` updated to exclude `.tfstate`, `terraform.tfvars`, `.terraform/`

### 4.2 Init Command

```bash
cd infrastructure/terraform/

# Initialize backend and download providers
terraform init \
  -backend-config="bucket=amg-campaign-tf-state-q3" \
  -backend-config="prefix=amg-campaign-2026-06-29" \
  -upgrade

# Expected output:
# Terraform has been successfully configured!
# The Terraform backend has been initialized.
```

### 4.3 Post-Init Verification

- [ ] `.terraform/` directory created
- [ ] `terraform/.terraform/terraform.tfstate` exists (local state, temporary)
- [ ] Remote state backend confirmed in `.terraform/` config
- [ ] `terraform plan` runs without provider errors
- [ ] State locking works (Terraform locks remote state during operations)

---

## 5. Terraform Plan (Dry-Run)

Before `terraform apply`, run:

```bash
terraform plan -out=tfplan

# Review output:
# - 40–60 resources to be created (BigQuery datasets, Spanner, Cloud Run, IAM, etc.)
# - No resources to be destroyed
# - No resource replacements
```

**Expected resource count:** ~55 new resources (see resource inventory in §6)

**Approval:** Infrastructure Lead reviews plan; approves before apply.

---

## 6. Resource Inventory (E5-T2 to E5-T7)

| Resource Type | Count | Status | Terraform File |
|---------------|-------|--------|-----------------|
| BigQuery Datasets | 3 (raw, curated, benchmark_metrics) | Create in E5-T4 | bigquery.tf |
| BigQuery Tables | 25+ (from E3-T1 schema) | Create in E5-T4 | bigquery.tf |
| Spanner Instance | 1 (amg-campaign-spanner) | Create in E5-T7 | spanner.tf |
| Spanner Database | 1 (memory_db) | Create in E5-T7 | spanner.tf |
| Cloud Run Service | 1 (amg-campaign-agents) | Create in E5-T7 | cloudrun.tf |
| Service Accounts | 3 (svc, tf, scheduler) | Create in E5-T5 | iam.tf |
| IAM Role Bindings | 20+ | Create in E5-T5 | iam.tf |
| GCS Buckets | 3 (tf-state, corpus, audit-logs) | Create in E5-T2/T5 | storage.tf |
| Secret Manager Secrets | 4 (Slack, Calendar, Jira, GitHub tokens) | Create in E5-T5 | secrets.tf |
| Cloud Budget | 1 (USD 300) | Create in E5-T4 | budget.tf |
| Budget Alerts | 4 (50%, 75%, 90%, 100%) | Create in E5-T4 | monitoring.tf |
| Cloud Scheduler Jobs | 2–3 (if applicable for E6/E7) | Create in E6–E7 | scheduler.tf |
| Cloud Monitoring Dashboards | 2–3 (campaign, cost, observability) | Create in E5-T4 | monitoring.tf |
| **TOTAL** | **~55 resources** | Planned | Multiple files |

---

## 7. Terraform Execution Flow

```
E5-T1 Complete: Variables resolved
         ↓
E5-T2 START: Terraform init
         ↓
  1. GCS backend created
  2. terraform init (backend initialized)
  3. terraform plan (dry-run; ~55 resources)
  4. Infrastructure Lead approves plan
         ↓
E5-T3: Enable APIs (parallel with T2)
         ↓
E5-T4: Budget & monitoring (depends on T3)
         ↓
E5-T5: IAM & secrets (depends on T3)
         ↓
E5-T6: Labels (depends on T2)
         ↓
E5-T7: Apply (trigger: terraform apply)
         ↓
  • BigQuery datasets/tables created
  • Spanner instance and database created
  • Cloud Run service deployed
  • IAM bindings applied
  • Budget alerts activated
  • Secrets stored in Secret Manager
         ↓
E5-T8: Gate review (validation)
```

---

## 8. State Management and Locking

### 8.1 State Locking

Terraform automatically locks remote state during operations to prevent concurrent modifications.

```bash
# Manual state lock inspection (if needed)
gsutil stat gs://amg-campaign-tf-state-q3/amg-campaign-2026-06-29/default.tfstate

# Force unlock (only in emergencies; use with extreme caution)
terraform force-unlock <LOCK_ID>
```

### 8.2 State Backup and Recovery

**Automatic:**
- GCS versioning keeps up to 5 old states; older versions deleted after 30 days
- Cloud Audit Logs record all state access (who, when, what changed)

**Manual backup (before apply):**
```bash
gsutil cp gs://amg-campaign-tf-state-q3/amg-campaign-2026-06-29/default.tfstate \
  gs://amg-campaign-audit-logs/backups/state-backup-$(date +%Y%m%d-%H%M%S).tfstate
```

### 8.3 Disaster Recovery

If state file is corrupted or lost:
1. Restore from GCS version history
2. If versions unavailable, import existing resources: `terraform import`
3. Last resort: recreate infrastructure (unlikely for campaign; clean slate available)

---

## 9. Post-Init Handoff (to E5-T3, E5-T4, E5-T5)

After `terraform init` succeeds:

1. **E5-T3 Owner:** Enable required APIs (no API call fails due to missing provider)
2. **E5-T4 Owner:** Create budget alert resources (ready to be added to terraform.tf)
3. **E5-T5 Owner:** Create service accounts and IAM bindings (via Terraform)
4. **E5-T7 Owner:** Provision runtime services (Cloud Run, Spanner; depends on T3, T4, T5)

All three teams (T3, T4, T5) can work in parallel **after T2 completes**.

---

## 10. Troubleshooting

| Error | Cause | Resolution |
|-------|-------|-----------|
| "Failed to read backend" | GCS bucket not accessible | Verify IAM roles for amg-campaign-tf SA |
| "backend initialization required" | `.terraform/` missing | Run `terraform init` again |
| "bucket already exists" | Bucket from previous run | Check versioning; restore from backup if needed |
| "Quota exceeded: Compute" | Regional quota exhausted | Request quota increase; deploy to secondary region |
| "Permission denied" | amg-campaign-tf SA lacks role | Check E5-T5 IAM bindings |

---

## 11. Sign-Off Checklist

| Item | Owner | Sign-Off | Date |
|------|-------|----------|------|
| GCS backend bucket created | Infrastructure Lead | ☐ | ____ |
| `terraform init` succeeded | Infrastructure Lead | ☐ | ____ |
| `terraform plan` reviewed (55 resources) | Infrastructure Lead | ☐ | ____ |
| `.terraform/` directory valid | Infrastructure Lead | ☐ | ____ |
| Remote state backend accessible | Infrastructure Lead | ☐ | ____ |
| Ready for E5-T3, T4, T5 parallel work | Program Manager | ☐ | ____ |

---

## 12. Campaign Terraform Workspace FROZEN

Effective after E5-T2 sign-off:
- Backend bucket location is immutable
- Terraform version is pinned to `>= 1.6, < 2.0`
- Provider versions are pinned to `~> 5.20`
- State file structure is frozen (no restructuring without explicit plan)

**Note:** Terraform code can evolve in E5-T3 through E7, but the backend foundation is locked.
