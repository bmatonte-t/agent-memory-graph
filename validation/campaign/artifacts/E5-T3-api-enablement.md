# E5-T3 — API Enablement and Artifact Registry Setup

**Epic:** E5 — Deferred GCP Bootstrap and Runtime Provisioning
**Task:** E5-T3
**Date:** 2026-07-09
**Status:** Approved
**Owner:** Infrastructure Lead

---

## 1. Objective

Enable all required GCP APIs on the campaign project. These must be enabled **before any service provisioning** (BigQuery, Spanner, Cloud Run, etc.). Additionally, set up Artifact Registry for container image storage and retrieval.

**Blocking:** E5-T4, E5-T5, E5-T6, E5-T7 all depend on API enablement.

---

## 2. Required APIs for Campaign

### 2.1 Core Data and Compute APIs

| API | Service Name | Required For | Critical? |
|-----|--------------|--------------|-----------|
| `bigquery.googleapis.com` | BigQuery API | Data warehousing; KPI queries | ✅ YES |
| `spanner.googleapis.com` | Cloud Spanner API | Graph memory storage | ✅ YES |
| `cloudrun.googleapis.com` | Cloud Run API | Agent backend execution | ✅ YES |
| `cloudfunctions.googleapis.com` | Cloud Functions API | ETL/data ingestion triggers | ⚠ Conditional (if used in E6) |
| `dataflow.googleapis.com` | Cloud Dataflow API | Batch data pipelines (E6) | ⚠ Conditional |

### 2.2 Integration and Orchestration APIs

| API | Service Name | Required For | Critical? |
|-----|--------------|--------------|-----------|
| `cloudscheduler.googleapis.com` | Cloud Scheduler API | Scheduled benchmark runs (E6/E7) | ✅ YES |
| `container.googleapis.com` | Kubernetes Engine API | Container management (for Cloud Run) | ✅ YES |
| `compute.googleapis.com` | Compute Engine API | Infrastructure networking | ✅ YES |

### 2.3 Storage and Artifact APIs

| API | Service Name | Required For | Critical? |
|-----|--------------|--------------|-----------|
| `storage-api.googleapis.com` | Cloud Storage API | Corpus storage, state backup | ✅ YES |
| `artifactregistry.googleapis.com` | Artifact Registry API | Container image registry | ✅ YES |

### 2.4 Logging, Audit, and Monitoring APIs

| API | Service Name | Required For | Critical? |
|-----|--------------|--------------|-----------|
| `logging.googleapis.com` | Cloud Logging API | T3 audit log persistence | ✅ YES |
| `monitoring.googleapis.com` | Cloud Monitoring API | Dashboards, metrics, alerts (E4-T4) | ✅ YES |
| `cloudtrace.googleapis.com` | Cloud Trace API | Distributed tracing (E4-T4) | ✅ YES |

### 2.5 Security and Access APIs

| API | Service Name | Required For | Critical? |
|-----|--------------|--------------|-----------|
| `iam.googleapis.com` | Identity and Access Management API | Service account management (E5-T5) | ✅ YES |
| `secretmanager.googleapis.com` | Secret Manager API | Integration credentials (E2-T3, E5-T5) | ✅ YES |
| `cloudkms.googleapis.com` | Cloud KMS API | Encryption key management | ⚠ Conditional |

### 2.6 Resource Management and Billing APIs

| API | Service Name | Required For | Critical? |
|-----|--------------|--------------|-----------|
| `cloudresourcemanager.googleapis.com` | Cloud Resource Manager API | Project and label management | ✅ YES |
| `billing.googleapis.com` | Cloud Billing API | Budget alerts (E5-T4) | ✅ YES |

### 2.7 Additional Utility APIs

| API | Service Name | Required For | Critical? |
|-----|--------------|--------------|-----------|
| `serviceusage.googleapis.com` | Service Usage API | Enable/disable other APIs | ✅ YES |
| `servicenetworking.googleapis.com` | Service Networking API | Private service connections (if needed) | ⚠ Conditional |

---

## 3. API Enablement Procedure

### 3.1 Via `gcloud` CLI (Recommended)

```bash
#!/bin/bash
# enable_apis.sh

PROJECT_ID={{PROJECT_ID}}

# Critical APIs (must enable first)
CRITICAL_APIS=(
  "bigquery.googleapis.com"
  "spanner.googleapis.com"
  "cloudrun.googleapis.com"
  "cloudscheduler.googleapis.com"
  "container.googleapis.com"
  "compute.googleapis.com"
  "storage-api.googleapis.com"
  "artifactregistry.googleapis.com"
  "logging.googleapis.com"
  "monitoring.googleapis.com"
  "cloudtrace.googleapis.com"
  "iam.googleapis.com"
  "secretmanager.googleapis.com"
  "cloudresourcemanager.googleapis.com"
  "billing.googleapis.com"
  "serviceusage.googleapis.com"
)

# Optional APIs (enable if applicable)
OPTIONAL_APIS=(
  "cloudfunctions.googleapis.com"
  "dataflow.googleapis.com"
  "cloudkms.googleapis.com"
  "servicenetworking.googleapis.com"
)

# Enable critical APIs
for api in "${CRITICAL_APIS[@]}"; do
  echo "Enabling $api..."
  gcloud services enable "$api" --project="$PROJECT_ID"
  if [ $? -ne 0 ]; then
    echo "ERROR: Failed to enable $api"
    exit 1
  fi
done

echo "All critical APIs enabled successfully!"

# Optional: enable optional APIs (non-blocking if they fail)
for api in "${OPTIONAL_APIS[@]}"; do
  echo "Enabling optional API: $api..."
  gcloud services enable "$api" --project="$PROJECT_ID" || echo "Skipping $api (optional)"
done

echo "API enablement complete."
```

### 3.2 Via Terraform (Alternative)

```hcl
# terraform/main.tf
resource "google_project_service" "bigquery" {
  project = var.project_id
  service = "bigquery.googleapis.com"
  disable_on_destroy = true  # Keep service enabled if Terraform is destroyed
}

resource "google_project_service" "spanner" {
  project = var.project_id
  service = "spanner.googleapis.com"
  depends_on = [google_project_service.bigquery]
}

resource "google_project_service" "cloudrun" {
  project = var.project_id
  service = "cloudrun.googleapis.com"
  depends_on = [google_project_service.bigquery]
}

resource "google_project_service" "storage" {
  project = var.project_id
  service = "storage-api.googleapis.com"
}

# ... define remaining APIs similarly
```

Run: `terraform apply -target=google_project_service.bigquery -target=google_project_service.spanner ...`

### 3.3 Verification

```bash
# List enabled APIs
gcloud services list --enabled --project={{PROJECT_ID}}

# Verify specific API is enabled
gcloud services describe bigquery.googleapis.com --project={{PROJECT_ID}}
```

**Expected output:** `state: ENABLED`

---

## 4. Artifact Registry Setup

### 4.1 Create Docker Repository

```bash
# Create Artifact Registry repository
gcloud artifacts repositories create amg-campaign \
  --repository-format=docker \
  --location={{REGION}} \
  --project={{PROJECT_ID}} \
  --description="Campaign Docker images for agents" \
  --labels=campaign=validation-2026,env=campaign

# Verify creation
gcloud artifacts repositories describe amg-campaign \
  --location={{REGION}} \
  --project={{PROJECT_ID}}

# Expected output:
# name: projects/{{PROJECT_ID}}/locations/{{REGION}}/repositories/amg-campaign
# format: DOCKER
```

### 4.2 Repository URI

**Format:** `{{REGION}}-docker.pkg.dev/{{PROJECT_ID}}/amg-campaign`

**Example:** `us-central1-docker.pkg.dev/amg-validation-2026-07-q3/amg-campaign`

**Used for:**
- Pushing agent backend image: `docker push {{REGION}}-docker.pkg.dev/{{PROJECT_ID}}/amg-campaign/agents:latest`
- Cloud Run deployment: references this image URI

### 4.3 Access Control

```bash
# Grant amg-campaign-svc SA permission to pull images
gcloud artifacts repositories add-iam-policy-binding amg-campaign \
  --location={{REGION}} \
  --member=serviceAccount:amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/artifactregistry.reader \
  --project={{PROJECT_ID}}

# Grant amg-campaign-tf SA permission to push/manage images
gcloud artifacts repositories add-iam-policy-binding amg-campaign \
  --location={{REGION}} \
  --member=serviceAccount:amg-campaign-tf@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/artifactregistry.admin \
  --project={{PROJECT_ID}}
```

### 4.4 Docker Configuration (Local Dev)

Before pushing images, configure Docker to authenticate with Artifact Registry:

```bash
# Authenticate gcloud
gcloud auth configure-docker {{REGION}}-docker.pkg.dev

# Expected: Updated ~/.docker/config.json with Artifact Registry credentials
```

---

## 5. API Enablement Checklist

| API | Status | Verified By | Date |
|-----|--------|-------------|------|
| bigquery.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| spanner.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| cloudrun.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| cloudscheduler.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| container.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| compute.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| storage-api.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| artifactregistry.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| logging.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| monitoring.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| cloudtrace.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| iam.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| secretmanager.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| cloudresourcemanager.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| billing.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |
| serviceusage.googleapis.com | ☐ Enabled | Infrastructure Lead | ____ |

---

## 6. Artifact Registry Checklist

| Item | Status | Owner | Sign-Off | Date |
|------|--------|-------|----------|------|
| Repository created (amg-campaign) | ☐ YES | Infrastructure Lead | ☐ | ____ |
| Repository URI confirmed | ☐ YES | Infrastructure Lead | ☐ | ____ |
| IAM: amg-campaign-svc has `artifactregistry.reader` | ☐ YES | Infrastructure Lead | ☐ | ____ |
| IAM: amg-campaign-tf has `artifactregistry.admin` | ☐ YES | Infrastructure Lead | ☐ | ____ |
| Docker auth configured locally | ☐ YES | Backend Engineer | ☐ | ____ |

---

## 7. Quota Verification

Before provisioning resources, verify GCP quotas are sufficient:

```bash
# Check Spanner quota
gcloud compute project-info describe --project={{PROJECT_ID}} \
  --format='value(quotas[name=SPANNER_INSTANCES_PER_PROJECT])'

# Check BigQuery quota
gcloud compute project-info describe --project={{PROJECT_ID}} \
  --format='value(quotas[name=BIGQUERY_DATASETS_PER_PROJECT])'

# Check Cloud Run quota
gcloud compute project-info describe --project={{PROJECT_ID}} \
  --format='value(quotas[name=CLOUD_RUN_SERVICES_PER_PROJECT])'
```

**Expected:** Quotas >= 1 for each critical resource type (default quotas usually sufficient).

**If quota exceeded:** Request increase via GCP Console > Quotas & System Limits.

---

## 8. Troubleshooting

| Error | Cause | Resolution |
|-------|-------|-----------|
| "Permission denied" enabling API | IAM role missing | Verify account has `roles/serviceusage.serviceUsageAdmin` |
| "Quota exceeded: Spanner instances" | Regional quota exhausted | Request quota increase or use secondary region |
| "Artifact Registry not found" | Repository doesn't exist | Run `gcloud artifacts repositories create` |
| "Docker auth failed" | credentials not configured | Run `gcloud auth configure-docker {{REGION}}-docker.pkg.dev` |

---

## 9. Sign-Off

| Item | Owner | Sign-Off | Date |
|------|-------|----------|------|
| All 16 critical APIs enabled | Infrastructure Lead | ☐ | ____ |
| `gcloud services list` shows all APIs as ENABLED | Infrastructure Lead | ☐ | ____ |
| Artifact Registry repository created | Infrastructure Lead | ☐ | ____ |
| IAM roles assigned for Artifact Registry | Infrastructure Lead | ☐ | ____ |
| Docker auth configured | Backend Engineer | ☐ | ____ |
| Ready for E5-T4, T5, T7 to proceed | Program Manager | ☐ | ____ |
