# Infrastructure

## Terraform Module

All infrastructure is provisioned by a single Terraform module at `infrastructure/terraform/`. The module is workspace-aware: `terraform.workspace` selects the environment (`dev`, `intg`, `prod`) and drives all env-specific values via `lookup(var.map, terraform.workspace)`.

### Files

| File | What it provisions |
|---|---|
| `main.tf` | Cloud Run service, service IAM binding, locals |
| `spanner.tf` | Spanner instance, Spanner database (+ migrations), Spanner SA IAM |
| `iam.tf` | Product SA and Spanner SA, project-level IAM roles |
| `secrets.tf` | Secret Manager secrets for Spanner credentials and app config |
| `monitoring.tf` | Two alert policies: high error rate and high p99 latency |
| `registry.tf` | Artifact Registry Docker repository, IAM bindings for SA and CI |
| `variables.tf` | All variable declarations with descriptions and defaults |
| `outputs.tf` | Cloud Run URL, SA emails |
| `config.yaml.tpl` | Template for the `app-config` secret content |

### Workspaces

```bash
# One-time workspace setup (per state bucket)
terraform workspace new dev
terraform workspace new intg
terraform workspace new prod

# Switch workspace before plan/apply
terraform workspace select dev
terraform plan -var-file=terraform.tfvars
```

The workspace name is exposed as `local.environment` and drives:
- Spanner processing units (100 PU dev/intg, 200 PU prod)
- Cloud Run min/max instances
- Deletion protection on Spanner database (off in dev, on in intg/prod)
- Resource labels (`environment = local.environment`)

### State Backend

State is stored in GCS. The bucket name is not hardcoded — it is passed at `terraform init` time:

```bash
terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="prefix=agent-memory-graph"
```

The prefix ensures each product uses its own subdirectory in the shared bucket. The bucket is provided by the Cosmos platform team and is shared across products.

---

## Resource Inventory

### Cloud Run Service (`main.tf`)

```hcl
resource "google_cloud_run_v2_service" "app" {
  name     = "agent-memory-graph"
  location = local.region
  project  = local.project_id

  template {
    service_account = google_service_account.product_sa.email

    containers {
      image = var.container_image

      resources {
        limits = { cpu = "2", memory = "4Gi" }
      }

      # Liveness probe — at /health, not /api/v1/health
      liveness_probe {
        http_get { path = "/health" }
        period_seconds = 30
      }

      # Startup probe — allows 5 min for Spanner cold start
      startup_probe {
        http_get { path = "/health" }
        failure_threshold = 10
        period_seconds    = 30
      }
    }

    scaling {
      min_instance_count = lookup(var.cloud_run_min_instances, local.environment, 1)
      max_instance_count = lookup(var.cloud_run_max_instances, local.environment, 10)
    }
  }
}
```

The `roles/run.invoker` IAM binding is **service-scoped** (not project-wide) and is granted only to the product SA:

```hcl
resource "google_cloud_run_v2_service_iam_member" "product_sa_invoker" {
  name   = google_cloud_run_v2_service.app.name
  role   = "roles/run.invoker"
  member = "serviceAccount:${google_service_account.product_sa.email}"
}
```

### Service Accounts (`iam.tf`)

Two SAs are created per environment:

**Product SA** (`agent-memory-graph-sa@{project}.iam.gserviceaccount.com`) — the Cloud Run identity. Project-level roles:
- `roles/logging.logWriter`
- `roles/cloudtrace.agent`
- `roles/monitoring.metricWriter`
- `roles/secretmanager.secretAccessor`

**Spanner SA** (`agent-memory-graph-spanner-sa@{project}.iam.gserviceaccount.com`) — used for cross-project Spanner access. Database-level role:
- `roles/spanner.databaseUser` (on the Spanner database, not project-wide)

The product SA can impersonate the Spanner SA via `roles/iam.serviceAccountTokenCreator`. This cross-project pattern means Spanner can live in a different project than Cloud Run if needed.

### Spanner (`spanner.tf`)

```
Instance: agent-memory-graph-{env}
Database: agent-memory-graph-{env}
```

- Processing units: 100 PU (dev/intg), 200 PU (prod)
- Deletion protection: disabled in dev, enabled in intg/prod
- Schema: 9 SQL migrations applied via a `null_resource` that triggers when migration file contents change (hashed via `filesha256`)
- Property graph: `AgentMemoryGraph` — declared in `migrations/008-property-graph.sql`

Migration trigger logic (content-based, not filename-based):
```hcl
triggers = {
  migrations_hash = sha256(join(",", [
    for f in sort(fileset("${path.module}/../../migrations", "*.sql")) :
    "${f}:${filesha256("${path.module}/../../migrations/${f}")}"
  ]))
}
```

### Secret Manager (`secrets.tf`)

Two secrets per environment:

| Secret name | Content | Rotation |
|---|---|---|
| `spanner-credentials` | Spanner SA JSON key | Manual |
| `app-config` | Rendered `config.yaml.tpl` | On Terraform apply |

The app config secret is rendered from `infrastructure/terraform/templates/config.yaml.tpl` using Terraform's `templatefile()`. It injects the Spanner project, instance, and database IDs, plus the company ID and auth mode.

### Artifact Registry (`registry.tf`)

```
Repository ID: agent-memory-graph
Format: DOCKER
Location: {region}
Path: {region}-docker.pkg.dev/{project_id}/agent-memory-graph/api:{tag}
```

Cleanup policies:
- Keep the 5 most recent tagged images
- Delete all untagged images

IAM bindings:
- Product SA: `roles/artifactregistry.reader` (pull at Cloud Run startup)
- CI/CD SA: `roles/artifactregistry.writer` (push during CI pipeline)

### Monitoring (`monitoring.tf`)

Two alert policies:

| Policy | Condition | Threshold |
|---|---|---|
| High error rate | `run.googleapis.com/request_count` with `response_code_class=5xx` | > 5% of requests over 5 min |
| High p99 latency | `run.googleapis.com/request_latencies` (p99) | > 5000 ms over 5 min |

Both policies accept `var.notification_channels` — a list of Cloud Monitoring notification channel resource IDs. Set to `[]` to receive alerts only in the Cloud Monitoring console.

---

## CI/CD Pipeline

### Pipeline overview

The GitLab CI pipeline (`.gitlab-ci.yml`) inherits the Cosmos shared `terraform-pipeline.yml` template and adds three custom jobs:

```
.pre stage
├── build-image     — Docker build + push to Artifact Registry
└── write-tfvars    — Generate terraform.tfvars from CI variables (artifact)

plan stage
└── terraform-plan  — terraform plan (dev workspace, all branches)

apply stage
├── terraform-apply (develop → dev)
├── terraform-apply (intg branch → intg, after advana workflow)
└── terraform-apply (main → prod, after human approval)
```

### `write-tfvars` job

The `write-tfvars` job runs in `.pre` and writes `infrastructure/terraform/terraform.tfvars` from CI variables. The file is exposed as a job artifact (expires in 1 hour) so downstream `plan` and `apply` jobs can read it.

This pattern keeps GCP project IDs out of the repository. The file is never committed.

### `build-image` job

Builds the Docker image and pushes it to Artifact Registry. The image is tagged with the commit SHA and `:latest`. The push output is parsed to extract the SHA digest, which is written to `build.env` as `TF_VAR_container_image` and injected into the Terraform stages as a dotenv artifact.

This ensures Cloud Run is always pinned to a specific image digest, never a mutable tag.

### Branch → environment mapping

| Branch | Workspace | Action |
|---|---|---|
| Feature branches | `dev` | `terraform plan` only |
| `develop` | `dev` | `terraform plan` + `terraform apply` |
| `intg` | `intg` | advana workflow + `terraform apply` |
| `main` | `prod` | Human approval gate + `terraform apply` |

### Required CI variables

Set in GitLab → Settings → CI/CD → Variables (mask all):

| Variable | Description |
|---|---|
| `GCP_PROJECT_ID_DEV` | GCP project ID, dev |
| `GCP_PROJECT_ID_INTG` | GCP project ID, intg |
| `GCP_PROJECT_ID_PROD` | GCP project ID, prod |
| `GCP_REGION` | GCP region (e.g., `us-east1`) |
| `TF_STATE_BUCKET` | GCS bucket for Terraform state |
| `GOOGLE_CREDENTIALS` | CI service account JSON key |
| `COMPANY_ID` | Tenant identifier (e.g., `latam-airlines`) |
| `NOTIFICATION_CHANNEL_IDS` | JSON array of monitoring channel IDs (e.g., `[]`) |

### CI service account roles

The service account backing `GOOGLE_CREDENTIALS` needs these roles in each GCP project:

```
roles/run.admin
roles/iam.serviceAccountUser
roles/artifactregistry.admin
roles/spanner.admin
roles/secretmanager.admin
roles/storage.admin          # Terraform state bucket
```

---

## Variables Reference

All Terraform input variables are declared in `variables.tf`. Key variables:

| Variable | Type | Description |
|---|---|---|
| `project_id` | `map(string)` | Cloud Run GCP project ID per environment |
| `spanner_project_id` | `map(string)` | Spanner GCP project ID per environment |
| `spanner_instance_id` | `map(string)` | Spanner instance ID per environment |
| `region` | `map(string)` | GCP region per environment |
| `container_image` | `string` | Fully qualified Docker image URI with SHA digest |
| `company_id` | `string` | Tenant identifier |
| `auth_mode` | `string` | `internal` (ABAC) or `external` |
| `cicd_sa_email` | `map(string)` | CI service account email per environment |
| `notification_channels` | `list(string)` | Cloud Monitoring notification channel IDs |
| `cloud_run_min_instances` | `map(number)` | Min Cloud Run instances per environment |
| `cloud_run_max_instances` | `map(number)` | Max Cloud Run instances per environment |

See `infrastructure/terraform/terraform.tfvars.example` for the complete annotated example.

---

## Outputs

After `terraform apply`, these outputs are available:

| Output | Description |
|---|---|
| `cloud_run_url` | HTTPS URL of the Cloud Run service |
| `product_sa_email` | Product SA email (Cloud Run identity) |
| `spanner_sa_email` | Spanner SA email |
| `artifact_registry_url` | Base URL for Docker images |

```bash
terraform output -raw cloud_run_url
# e.g. https://agent-memory-graph-xxxxxxxxxxxx-ue.a.run.app
```
