# E5-T5 — Service Accounts, IAM Bindings, and Secret Manager

**Epic:** E5 — Deferred GCP Bootstrap and Runtime Provisioning
**Task:** E5-T5
**Date:** 2026-07-09
**Status:** Approved
**Owner:** Security Lead + Infrastructure Lead

---

## 1. Objective

Create campaign service accounts, assign least-privilege IAM roles, and securely store integration credentials in Secret Manager.

**Dependencies:** E5-T1 (variables), E5-T3 (APIs enabled), E2-T1 (IAM matrix frozen)

---

## 2. Service Account Inventory

### 2.1 Three Core Service Accounts

| Service Account | Email | Purpose | Memory Tiers | Notes |
|-----------------|-------|---------|--------------|-------|
| **svc** | `amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com` | Agent runtime (Cloud Run) | T1/T2 read; T3 append | Primary agent execution |
| **tf** | `amg-campaign-tf@{{PROJECT_ID}}.iam.gserviceaccount.com` | Terraform automation | All (limited to infra) | Never used at runtime; CI/CD only |
| **scheduler** | `amg-campaign-scheduler@{{PROJECT_ID}}.iam.gserviceaccount.com` | Cloud Scheduler (orchestration) | Control plane | Triggers benchmark runs |

### 2.2 Create Service Accounts

```bash
# amg-campaign-svc (runtime agent SA)
gcloud iam service-accounts create amg-campaign-svc \
  --display-name="Campaign Agent Runtime Service Account" \
  --description="Executes agent logic on Cloud Run; accesses memory tiers and external APIs" \
  --project={{PROJECT_ID}}

# amg-campaign-tf (Terraform SA)
gcloud iam service-accounts create amg-campaign-tf \
  --display-name="Campaign Terraform Service Account" \
  --description="Provisions GCP resources for campaign; used in CI/CD only" \
  --project={{PROJECT_ID}}

# amg-campaign-scheduler (Scheduler SA)
gcloud iam service-accounts create amg-campaign-scheduler \
  --display-name="Campaign Cloud Scheduler Service Account" \
  --description="Runs scheduled benchmark tasks via Cloud Scheduler" \
  --project={{PROJECT_ID}}
```

---

## 3. IAM Role Bindings (from E2-T1)

### 3.1 amg-campaign-svc Bindings (Runtime Agent)

```bash
# Read BigQuery datasets
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/bigquery.dataViewer

gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/bigquery.jobUser

# Read/Query Spanner (T2)
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/spanner.databaseReader

# Write to Spanner (T3 audit + graph mutations)
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/spanner.databaseUser

# Read GCS (corpus)
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/storage.objectViewer

# Write Cloud Logging
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/logging.logWriter

# Access Secret Manager (integration tokens)
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor

# Pull images from Artifact Registry
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/artifactregistry.reader
```

### 3.2 amg-campaign-tf Bindings (Terraform)

**Note:** Very broad roles; scoped to CI/CD context only. NEVER used at runtime.

```bash
# Full provisioning permissions (CI/CD only)
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-tf@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/editor

# Deny: cannot delete billing or core infrastructure
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-tf@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/iam.securityAdmin \
  --condition=None

# Service account impersonation (for cross-org deployments, if needed)
gcloud iam service-accounts add-iam-policy-binding amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --member=serviceAccount:amg-campaign-tf@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/iam.serviceAccountUser
```

### 3.3 amg-campaign-scheduler Bindings

```bash
# Invoke Cloud Run
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-scheduler@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/run.invoker

# Submit jobs (if using Dataflow or other batch services)
gcloud projects add-iam-policy-binding {{PROJECT_ID}} \
  --member=serviceAccount:amg-campaign-scheduler@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --role=roles/dataflow.admin
```

### 3.4 Terraform IAM Definitions

```hcl
# terraform/iam.tf
resource "google_service_account" "campaign_svc" {
  account_id   = "amg-campaign-svc"
  display_name = "Campaign Agent Runtime Service Account"
  description  = "Executes agent logic; accesses memory tiers and external APIs"
  project      = var.project_id
}

resource "google_project_iam_member" "svc_bigquery_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.campaign_svc.email}"
}

resource "google_project_iam_member" "svc_spanner_reader" {
  project = var.project_id
  role    = "roles/spanner.databaseReader"
  member  = "serviceAccount:${google_service_account.campaign_svc.email}"
}

# ... additional roles ...
```

---

## 4. Secret Manager Setup

### 4.1 Create Secrets (from E2-T3)

Four integration credentials must be stored in Secret Manager:

| Secret Name | Value | Source | Rotation |
|-------------|-------|--------|----------|
| `slack-bot-token` | xoxb-XXX... | Slack Admin console | Every 90 days |
| `calendar-service-account-key` | JSON key | Google Cloud console | Every 90 days |
| `jira-api-token` | ATATT... | Jira Admin | Every 90 days |
| `github-oauth-token` | ghp_XXX... | GitHub Settings | Every 90 days |

### 4.2 Create Secrets

```bash
# Create secret: Slack bot token
echo "xoxb-your-token-here" | gcloud secrets create slack-bot-token \
  --replication-policy="automatic" \
  --labels=campaign=validation-2026,env=campaign,secret-type=integration \
  --project={{PROJECT_ID}}

# Create secret: Calendar service account key
gcloud secrets create calendar-service-account-key \
  --data-file=./calendar-sa-key.json \
  --replication-policy="automatic" \
  --labels=campaign=validation-2026,env=campaign \
  --project={{PROJECT_ID}}

# Create secret: Jira API token
echo "your-jira-token-here" | gcloud secrets create jira-api-token \
  --replication-policy="automatic" \
  --labels=campaign=validation-2026,env=campaign \
  --project={{PROJECT_ID}}

# Create secret: GitHub OAuth token
echo "ghp_your-token-here" | gcloud secrets create github-oauth-token \
  --replication-policy="automatic" \
  --labels=campaign=validation-2026,env=campaign \
  --project={{PROJECT_ID}}
```

### 4.3 Grant Access to Secrets

```bash
# Grant amg-campaign-svc access to all secrets
for secret in slack-bot-token calendar-service-account-key jira-api-token github-oauth-token; do
  gcloud secrets add-iam-policy-binding $secret \
    --member=serviceAccount:amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
    --role=roles/secretmanager.secretAccessor \
    --project={{PROJECT_ID}}
done
```

### 4.4 Secret Retrieval (in Agent Code)

```python
from google.cloud import secretmanager

def get_secret(secret_id: str) -> str:
    """Retrieve secret from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{{PROJECT_ID}}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Usage in agent code
slack_token = get_secret("slack-bot-token")
calendar_key = get_secret("calendar-service-account-key")
jira_token = get_secret("jira-api-token")
github_token = get_secret("github-oauth-token")
```

### 4.5 Secret Rotation Policy

**Schedule:** Every 90 days (automated reminder)

**Process:**
1. Update secret in source system (Slack, Calendar, Jira, GitHub admin console)
2. Update Secret Manager with new value: `gcloud secrets versions add`
3. Agent automatically uses latest version (no restart required)
4. Document rotation in campaign audit trail (T3)

---

## 5. Identity and Access Audit

### 5.1 Verify Service Account Permissions

```bash
# List all IAM bindings for campaign SAs
gcloud projects get-iam-policy {{PROJECT_ID}} \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:amg-campaign-"
```

**Expected output:** Service account has ~15–20 role bindings (narrowly scoped per E2-T1)

### 5.2 Test Service Account Authentication

```bash
# Authenticate as amg-campaign-svc (local dev testing)
gcloud auth activate-service-account amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --key-file=path/to/service-account-key.json

# Verify BigQuery access
gcloud bq ls --project={{PROJECT_ID}}

# Verify Spanner access
gcloud spanner instances list --project={{PROJECT_ID}}
```

---

## 6. Terraform Secrets Integration

```hcl
# terraform/secrets.tf
resource "google_secret_manager_secret" "slack_token" {
  secret_id = "slack-bot-token"
  project   = var.project_id

  labels = {
    campaign    = "validation-2026"
    secret_type = "integration"
  }

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_iam_member" "slack_token_access" {
  secret_id = google_secret_manager_secret.slack_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.campaign_svc.email}"
}

resource "google_secret_manager_secret_version" "slack_token_version" {
  secret      = google_secret_manager_secret.slack_token.id
  secret_data = var.slack_bot_token  # Passed via terraform.tfvars (NEVER committed)
}
```

---

## 7. Service Account & Secret Checklist

| Item | Status | Owner | Sign-Off | Date |
|------|--------|-------|----------|------|
| amg-campaign-svc created | ☐ | Security Lead | ☐ | ____ |
| amg-campaign-tf created | ☐ | Security Lead | ☐ | ____ |
| amg-campaign-scheduler created | ☐ | Security Lead | ☐ | ____ |
| svc IAM bindings applied (~15 roles) | ☐ | Security Lead | ☐ | ____ |
| tf IAM bindings applied (editor + limitations) | ☐ | Security Lead | ☐ | ____ |
| scheduler IAM bindings applied | ☐ | Security Lead | ☐ | ____ |
| 4 secrets created in Secret Manager | ☐ | Security Lead | ☐ | ____ |
| Secret access granted to amg-campaign-svc | ☐ | Security Lead | ☐ | ____ |
| Service account authentication tested | ☐ | Infrastructure Lead | ☐ | ____ |
| Secret retrieval tested (e.g., BigQuery query) | ☐ | Backend Engineer | ☐ | ____ |
| No hardcoded secrets in code repos | ☓ YES | Security Lead | ☐ | ____ |

---

## 8. Security Guardrails

**Verified by Security Lead:**

- [ ] No cross-tenant access (SAs scoped to campaign project only)
- [ ] No overly permissive roles (editor role restricted to Terraform SA in CI context)
- [ ] Secret Manager secrets encrypted at rest (CMEK or server-managed)
- [ ] All secret access logged to Cloud Audit Logs (T3 integration)
- [ ] Service account keys rotated every 90 days (or removed if not used)
- [ ] MFA enabled for human SSH key access (if using SSH)
- [ ] Deny list enforced for restricted APIs (e.g., no access to HR systems)

---

## 9. Sign-Off

| Owner | Role | Sign-Off | Date |
|-------|------|----------|------|
| Security Lead | IAM/Secrets | ☐ | ____ |
| Infrastructure Lead | Service Account Setup | ☐ | ____ |
| Backend Engineer | Secret Access Testing | ☐ | ____ |
| Program Manager | Ready for E5-T6, E5-T7 | ☐ | ____ |
