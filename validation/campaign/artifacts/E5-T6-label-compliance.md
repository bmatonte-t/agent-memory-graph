# E5-T6 — Label Compliance and Policy Enforcement

**Epic:** E5 — Deferred GCP Bootstrap and Runtime Provisioning
**Task:** E5-T6
**Date:** 2026-07-09
**Status:** Approved
**Owner:** Infrastructure Lead

---

## 1. Objective

Apply campaign labels to all provisioned resources and enforce label policies via Terraform and GCP Organization Policy. These labels enable cost attribution, lifecycle management, and governance tracking (frozen in E1-T5).

**Dependencies:** E5-T2 (Terraform workspace), E5-T3 (APIs enabled)

---

## 2. Campaign Label Schema (from E1-T5, Frozen)

### 2.1 Mandatory Labels (5 labels, required on ALL resources)

| Label | Key | Value | Enforced By | Purpose |
|-------|-----|-------|-------------|---------|
| **Campaign** | `campaign` | `validation-2026` | Org Policy | Cost tracking, lifecycle grouping |
| **Owner** | `owner` | `product-team` | Org Policy | RACI ownership, escalation |
| **Environment** | `env` | `campaign` | Org Policy | Dev/staging/prod distinction |
| **TTL** | `ttl` | `6-weeks` | Cloud Scheduler | Auto-deletion after 2026-07-27 |
| **Auto-Delete** | `auto_delete` | `true` | Cloud Scheduler | Enable/disable auto-cleanup |

### 2.2 Optional Labels (informational, applied where relevant)

| Label | Key | Example Value | Purpose |
|-------|-----|----------------|---------|
| Created By | `created_by` | `terraform` | Automation tracking |
| Created At | `created_at` | `2026-07-09` | Timestamp for audit |
| Team | `team` | `data-science` | Cross-functional association |
| Cost Center | `cost_center` | `analytics-001` | Billing allocation |

---

## 3. Resource-Specific Label Application

### 3.1 Compute (Cloud Run)

```bash
gcloud run services update {{CLOUD_RUN_SERVICE}} \
  --update-labels=campaign=validation-2026,owner=product-team,env=campaign,ttl=6-weeks,auto_delete=true,created_by=terraform,created_at=2026-07-09 \
  --region={{REGION}} \
  --project={{PROJECT_ID}}
```

### 3.2 Storage (GCS Buckets)

```bash
# Backend state bucket
gsutil label ch -l campaign:validation-2026 gs://amg-campaign-tf-state-q3
gsutil label ch -l owner:product-team gs://amg-campaign-tf-state-q3
gsutil label ch -l env:campaign gs://amg-campaign-tf-state-q3
gsutil label ch -l ttl:6-weeks gs://amg-campaign-tf-state-q3
gsutil label ch -l auto_delete:true gs://amg-campaign-tf-state-q3

# Corpus bucket
gsutil label ch -l campaign:validation-2026 gs://amg-campaign-corpus-q3
gsutil label ch -l owner:product-team gs://amg-campaign-corpus-q3
gsutil label ch -l env:campaign gs://amg-campaign-corpus-q3

# Audit logs bucket
gsutil label ch -l campaign:validation-2026 gs://amg-campaign-audit-logs
gsutil label ch -l owner:product-team gs://amg-campaign-audit-logs
gsutil label ch -l env:campaign gs://amg-campaign-audit-logs
```

### 3.3 Databases (BigQuery & Spanner)

```bash
# BigQuery dataset labels
bq update --set_iam_policy={{POLICY_FILE}} raw_retail_public
bq update --description "Raw retail data" --labels=campaign:validation-2026,owner:product-team,env:campaign raw_retail_public

# Spanner instance labels
gcloud spanner instances update {{SPANNER_INSTANCE_ID}} \
  --update-labels=campaign=validation-2026,owner=product-team,env=campaign,ttl=6-weeks,auto_delete=true \
  --project={{PROJECT_ID}}
```

### 3.4 Terraform Centralized Labels

```hcl
# terraform/labels.tf
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

# Apply to all resources (example: Cloud Run)
resource "google_cloud_run_service" "agents" {
  name     = "{{CLOUD_RUN_SERVICE}}"
  location = var.region
  project  = var.project_id

  labels = local.campaign_labels

  template {
    spec {
      service_account_name = google_service_account.campaign_svc.email
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/amg-campaign/agents:latest"
      }
    }
  }
}

# Apply to BigQuery dataset
resource "google_bigquery_dataset" "benchmark_metrics" {
  dataset_id    = "benchmark_metrics"
  friendly_name = "Campaign Benchmark Metrics"
  project       = var.project_id

  labels = local.campaign_labels
}

# Apply to Spanner instance
resource "google_spanner_instance" "campaign" {
  name             = "{{SPANNER_INSTANCE_ID}}"
  config           = "multi-region-us"
  display_name     = "Campaign Memory Storage"
  num_nodes        = 1
  project          = var.project_id

  labels = local.campaign_labels
}
```

---

## 4. GCP Organization Policy (Label Enforcement)

### 4.1 Policy Definition

**Policy Name:** `require-campaign-labels`

**Enforces:** All resources in campaign project must have labels: `campaign`, `owner`, `env`

```yaml
name: require-campaign-labels
listPolicy:
  deniedValues:
    - "projects/{{PROJECT_ID}}/labels/campaign:*"  # Deny missing or wrong campaign value
    - "projects/{{PROJECT_ID}}/labels/owner:*"
    - "projects/{{PROJECT_ID}}/labels/env:*"
  allowedValues:
    - "projects/{{PROJECT_ID}}/labels/campaign:validation-2026"
    - "projects/{{PROJECT_ID}}/labels/owner:product-team"
    - "projects/{{PROJECT_ID}}/labels/env:campaign"
```

### 4.2 Apply Organization Policy

```bash
# Create constraint file
cat > require-labels.yaml <<EOF
name: organizations/{{ORG_ID}}/policies/gce.requireLabelSetting
spec:
  rules:
    - enforce: true
      condition:
        expression: "resource.labels.campaign=='validation-2026' && resource.labels.owner=='product-team' && resource.labels.env=='campaign'"
EOF

# Apply policy
gcloud resource-manager org-policies set-policy require-labels.yaml \
  --project={{PROJECT_ID}}
```

---

## 5. Label Compliance Audit

### 5.1 Audit Query (BigQuery)

```sql
-- Query Cloud Asset Inventory to find unlabeled resources
SELECT
  resource.type,
  resource.name,
  ARRAY_LENGTH(resource.labels) as label_count,
  resource.labels
FROM `{{PROJECT_ID}}.cloud_asset_inventory.resource_inventory`
WHERE project_id = '{{PROJECT_ID}}'
  AND (
    resource.labels IS NULL
    OR NOT EXISTS (
      SELECT 1 FROM UNNEST(resource.labels) label
      WHERE label.key = 'campaign' AND label.value = 'validation-2026'
    )
  )
ORDER BY resource.type;
```

### 5.2 Compliance Checklist

| Resource Type | Count | All Labeled? | Owner | Sign-Off | Date |
|---------------|-------|--------------|-------|----------|------|
| Cloud Run Services | 1 | ☐ | Infrastructure Lead | ☐ | ____ |
| GCS Buckets | 3 | ☐ | Infrastructure Lead | ☐ | ____ |
| BigQuery Datasets | 3 | ☐ | Data Lead | ☐ | ____ |
| Spanner Instance | 1 | ☐ | Infrastructure Lead | ☐ | ____ |
| Service Accounts | 3 | ☐ | Security Lead | ☐ | ____ |
| Secret Manager Secrets | 4 | ☐ | Security Lead | ☐ | ____ |
| Cloud Monitoring Dashboards | 2–3 | ☐ | Infrastructure Lead | ☐ | ____ |
| Cloud Scheduler Jobs | 1–2 | ☐ | Infrastructure Lead | ☐ | ____ |

---

## 6. Label Lifecycle Management

### 6.1 TTL Label (6-weeks auto-delete)

**Value:** `ttl=6-weeks`

**Interpretation:** Resource should be automatically deleted on or after 2026-07-27 (campaign end date)

**Implementation (Cloud Scheduler):**

```python
# cleanup_scheduler.py
# Runs daily at 23:59 UTC starting 2026-07-27

import datetime
from google.cloud import compute_v1, storage, bigquery

def cleanup_campaign_resources():
    """Delete resources with ttl=6-weeks after campaign end date."""

    campaign_end = datetime.datetime(2026, 7, 27, 23, 59, 59, tzinfo=datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)

    if now < campaign_end:
        print("Campaign not yet ended; skipping cleanup")
        return

    # Delete GCS buckets
    storage_client = storage.Client()
    for bucket in storage_client.list_buckets():
        labels = bucket.labels or {}
        if labels.get("campaign") == "validation-2026" and labels.get("ttl") == "6-weeks":
            print(f"Deleting bucket: {bucket.name}")
            bucket.delete(force=True)

    # Delete BigQuery datasets
    bq_client = bigquery.Client()
    for dataset in bq_client.list_datasets():
        labels = dataset.labels or {}
        if labels.get("campaign") == "validation-2026" and labels.get("ttl") == "6-weeks":
            print(f"Deleting dataset: {dataset.dataset_id}")
            bq_client.delete_dataset(dataset.dataset_id, delete_contents=True)

    # Delete Cloud Run services
    compute_client = compute_v1.ServicesClient()
    # ... similar logic for Cloud Run

    print("Campaign resource cleanup complete")
```

### 6.2 auto_delete Label (enable/disable)

**Value:** `auto_delete=true` (enabled) or `auto_delete=false` (disabled)

**Use case:** If resource should be preserved post-campaign, set `auto_delete=false` and it will not be deleted even if TTL expires.

---

## 7. Cost Attribution via Labels

### 7.1 Breakdown by Label

```sql
-- Cost by campaign
SELECT
  labels.value AS campaign,
  SUM(cost) AS total_cost_usd
FROM `{{BILLING_PROJECT}}.gcp_billing_export_v1.gcp_billing_export_{{MONTH}}`
WHERE labels.key = 'campaign'
GROUP BY campaign
ORDER BY total_cost_usd DESC;

-- Cost by owner
SELECT
  labels.value AS owner,
  SUM(cost) AS total_cost_usd
FROM `{{BILLING_PROJECT}}.gcp_billing_export_v1.gcp_billing_export_{{MONTH}}`
WHERE labels.key = 'owner'
GROUP BY owner;

-- Cost by environment
SELECT
  labels.value AS environment,
  SUM(cost) AS total_cost_usd
FROM `{{BILLING_PROJECT}}.gcp_billing_export_v1.gcp_billing_export_{{MONTH}}`
WHERE labels.key = 'env'
GROUP BY environment;
```

---

## 8. Label Compliance Checklist

| Item | Status | Owner | Sign-Off | Date |
|------|--------|-------|----------|------|
| All mandatory labels defined | ✓ | Infrastructure Lead | ☐ | ____ |
| Terraform labels.tf created | ☐ | Infrastructure Lead | ☐ | ____ |
| All 12 core resources labeled | ☐ | Infrastructure Lead | ☐ | ____ |
| Cloud Asset Inventory audit passed (0 unlabeled resources) | ☐ | Data Lead | ☐ | ____ |
| Organization Policy enforces labels (if available) | ☐ | Security Lead | ☐ | ____ |
| TTL auto-deletion scheduled | ☐ | Infrastructure Lead | ☐ | ____ |
| Cost attribution queries tested | ☐ | Data Lead | ☐ | ____ |
| Ready for E5-T7, E5-T8 | ☐ | Program Manager | ☐ | ____ |

---

## 9. Sign-Off

| Owner | Sign-Off | Date |
|-------|----------|------|
| Infrastructure Lead | ☐ | ____ |
| Data Lead | ☐ | ____ |
| Security Lead | ☐ | ____ |
| Program Manager | ☐ | ____ |
