# Deployment Guide

## LATAM Adoption Model

Agent Memory Graph is designed to be deployed project-by-project across LATAM's GCP organization. Each adopting team gets their own triad of GCP projects (dev / intg / prod) with a dedicated Cloud Run service, Spanner instance, and Artifact Registry.

### Adoption architecture

```
LATAM Organization
│
├── Team A: Revenue Analytics
│   ├── revenue-analytics-dev  → AMG Cloud Run (dev)  + Spanner (dev)
│   ├── revenue-analytics-intg → AMG Cloud Run (intg) + Spanner (intg)
│   └── revenue-analytics-prod → AMG Cloud Run (prod) + Spanner (prod)
│
├── Team B: Operations
│   ├── operations-dev  → AMG Cloud Run (dev)  + Spanner (dev)
│   ├── operations-intg → AMG Cloud Run (intg) + Spanner (intg)
│   └── operations-prod → AMG Cloud Run (prod) + Spanner (prod)
│
└── ... (each team adds their triad independently)
```

Each team's deployment is fully independent: no shared Spanner instances, no shared IAM, no cross-project data access. Teams can adopt AMG at their own pace.

### What gets deployed per project

Terraform provisions the following in each GCP project:

| Resource | Name | Notes |
|---|---|---|
| Cloud Run service | `agent-memory-graph` | 2 vCPU / 4 Gi, min 1 instance |
| Spanner instance | `agent-memory-graph-{env}` | 100 PU dev/intg, 200 PU prod |
| Spanner database | `agent-memory-graph-{env}` | 9 migrations applied on first apply |
| Artifact Registry | `agent-memory-graph` | Docker repository |
| Product SA | `agent-memory-graph-sa@{project}` | Cloud Run identity |
| Spanner SA | `agent-memory-graph-spanner-sa@{project}` | Cross-project Spanner access |
| Secret Manager secrets | `spanner-credentials`, `app-config` | Spanner key + app config YAML |
| Cloud Monitoring alerts | High error rate, high latency p99 | |

### Per-team onboarding steps

Follow these steps for each new adopting team:

**Step 1 — Confirm GCP projects exist**

The team should already have three GCP projects: `{team}-dev`, `{team}-intg`, `{team}-prod`. These are typically provisioned by the platform infra team.

Verify `cosmos-cicd-sa@{project}.iam.gserviceaccount.com` exists in each project.

**Step 2 — Bootstrap Artifact Registry (one-time, per project)**

Before the first CI pipeline run, create the Artifact Registry repository in each project. This is a one-time manual step:

```bash
# Replace variables with actual project IDs and region
GCP_REGION=us-east1

for PROJECT_ID in <DEV_PROJECT_ID> <INTG_PROJECT_ID> <PROD_PROJECT_ID>; do
  gcloud artifacts repositories create agent-memory-graph \
    --repository-format=docker \
    --location=${GCP_REGION} \
    --project=${PROJECT_ID} \
    --description="Docker images for agent-memory-graph Cloud Run service"
done
```

**Step 3 — Set GitLab CI/CD variables**

In the GitLab project (Settings → CI/CD → Variables), set these variables **masked**:

| Variable | Value |
|---|---|
| `GCP_PROJECT_ID_DEV` | `{team}-dev` project ID |
| `GCP_PROJECT_ID_INTG` | `{team}-intg` project ID |
| `GCP_PROJECT_ID_PROD` | `{team}-prod` project ID |
| `GCP_REGION` | `us-east1` (or team's region) |
| `TF_STATE_BUCKET` | Shared Terraform state GCS bucket |
| `GOOGLE_CREDENTIALS` | CI service account JSON key |
| `COMPANY_ID` | Team's organization identifier (e.g., `latam-airlines`) |
| `NOTIFICATION_CHANNEL_IDS` | `[]` (or list of Cloud Monitoring channel IDs) |

**Step 4 — Push to develop and verify dev apply**

Push any commit to the `develop` branch. The GitLab pipeline will:
1. Build and push the Docker image to the dev Artifact Registry
2. Generate `terraform.tfvars` from CI variables
3. Run `terraform plan` against the dev workspace
4. Run `terraform apply` — provisions all resources in the dev project

After the apply, the Cloud Run service URL is printed in the pipeline output. Verify:

```bash
curl https://<DEV_CLOUD_RUN_URL>/health
# Expected: {"status":"healthy","database":"initialized"}
```

**Step 5 — Promote through intg to prod**

```bash
# Merge develop → intg branch to trigger intg deployment
git checkout intg && git merge develop && git push origin intg

# After intg validation, merge intg → main to trigger prod gate
git checkout main && git merge intg && git push origin main
# GitLab pauses for human approval before applying to prod
```

**Step 6 — Configure MCP clients (optional)**

If the team uses Claude Code or another MCP client, point it at the Cloud Run service URL:

```json
{
  "mcpServers": {
    "agent-memory-graph": {
      "url": "https://<PROD_CLOUD_RUN_URL>/api/v1/mcp/invoke"
    }
  }
}
```

**Step 7 — Add team-specific MCP tools or docs (optional)**

Each team can extend the base AMG deployment with custom MCP tool configurations or documentation sources specific to their domain. Document these additions in the team's own repository.

---

## Manual Deployment (without CI)

Use this for initial testing or when CI is not yet set up.

### Prerequisites

- `gcloud` CLI authenticated with a service account that has the roles listed in `infrastructure/README.md`
- `terraform` >= 1.5
- Docker (for building images)

### Steps

```bash
# 1. Build and push the Docker image
cd /path/to/agent-memory-graph
GCP_REGION=us-east1
PROJECT_ID=<your-dev-project-id>
REGISTRY="${GCP_REGION}-docker.pkg.dev/${PROJECT_ID}/agent-memory-graph"
IMAGE="${REGISTRY}/api:$(git rev-parse --short HEAD)"

docker build -t "$IMAGE" .
docker push "$IMAGE"

# Capture the digest for Terraform
DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "$IMAGE")
echo "Image: $DIGEST"

# 2. Write terraform.tfvars
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars — replace placeholder tokens with real values:
# - project_id.dev = "<your-dev-project-id>"
# - spanner_project_id.dev = "<your-dev-project-id>"
# - container_image = "$DIGEST"
# - company_id = "your-org-id"
# (leave intg/prod as placeholders for now)

# 3. Initialize Terraform
terraform init \
  -backend-config="bucket=<your-tf-state-bucket>" \
  -backend-config="prefix=agent-memory-graph"

# Commit the generated .terraform.lock.hcl for reproducibility
git add .terraform.lock.hcl && git commit -m "chore: add terraform lock file"

# 4. Plan and apply dev
terraform workspace select dev || terraform workspace new dev
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars

# 5. Verify
CLOUD_RUN_URL=$(terraform output -raw cloud_run_url)
curl "${CLOUD_RUN_URL}/health"
```

---

## CI/CD Pipeline

The GitLab CI pipeline (`.gitlab-ci.yml`) runs three stages on every push:

| Stage | Job | Branch | Action |
|---|---|---|---|
| `.pre` | `build-image` | All | Docker build + push to Artifact Registry |
| `.pre` | `write-tfvars` | All | Write `terraform.tfvars` from CI variables |
| `plan` | `terraform-plan` | All | `terraform plan` (dev workspace) |
| `apply` | `terraform-apply` | `develop` | `terraform apply` (dev) |
| `apply` | `terraform-apply` | `intg` | advana workflow + `terraform apply` (intg) |
| `apply` | `terraform-apply` | `main` | Human approval gate + `terraform apply` (prod) |

The pipeline inherits the Cosmos shared `terraform-pipeline.yml` template from `latamairlines/data/data-ai-ops/cosmos/cicd-pipelines/base-pipelines`.

---

## Configuration Reference

The application is configured via `config.yaml` (defaults) with environment-specific overrides in `config.prod.yaml` and `config.dev.yaml`. Key settings:

```yaml
governance:
  weighting:
    enabled: true               # Enable cognitive weighting (set false for testing)
    action_count_threshold: 3   # Sessions with fewer actions get scaled weights
  authorization:
    enabled: true               # Enable ABAC (set false only in dev/testing)
    default_deny: true          # Deny-by-default (do not change)
  retry:
    max_attempts: 3             # Max Spanner retry attempts
    initial_backoff_seconds: 0.25
    max_backoff_seconds: 5.0

single_company:
  enabled: true
  company_id: "latam-airlines"  # Injected from COMPANY_ID CI variable
  auth_mode: "internal"         # internal = ABAC; external = delegate to external service
```

Environment variables that override config at startup:

| Variable | Description |
|---|---|
| `AGENT_MEMORY_GRAPH_SPANNER_PROJECT_ID` | GCP project hosting Spanner |
| `AGENT_MEMORY_GRAPH_SPANNER_INSTANCE_ID` | Spanner instance ID |
| `AGENT_MEMORY_GRAPH_SPANNER_DATABASE_ID` | Spanner database ID |
| `AGENT_MEMORY_GRAPH_SINGLE_COMPANY__ENABLED` | `"true"` or `"false"` |
| `AGENT_MEMORY_GRAPH_SINGLE_COMPANY__COMPANY_ID` | Tenant identifier |
| `AGENT_MEMORY_GRAPH_SINGLE_COMPANY__AUTH_MODE` | `internal` or `external` |
| `AGENT_MEMORY_GRAPH_ENVIRONMENT` | `dev`, `intg`, or `prod` |

These are injected at Cloud Run deployment time by Terraform from `main.tf`.
