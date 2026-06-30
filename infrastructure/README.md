# Infrastructure — agent-memory-graph

## Bootstrap Prerequisites (first-time only)

Before the first CI pipeline run, the Artifact Registry repository must exist in each target project.
The CI `build-image` job will fail if the repository is absent because Docker cannot push to a
non-existent registry.

Run the following commands once per environment (replace placeholder values with real project IDs and region):

```bash
# Run once per environment before the first CI pipeline
gcloud artifacts repositories create agent-memory-graph \
  --repository-format=docker \
  --location=${GCP_REGION} \
  --project=${GCP_PROJECT_ID_DEV} \
  --description="Docker images for agent-memory-graph Cloud Run service (dev)"
# Repeat for intg and prod projects
gcloud artifacts repositories create agent-memory-graph \
  --repository-format=docker \
  --location=${GCP_REGION} \
  --project=${GCP_PROJECT_ID_INTG} \
  --description="Docker images for agent-memory-graph Cloud Run service (intg)"
gcloud artifacts repositories create agent-memory-graph \
  --repository-format=docker \
  --location=${GCP_REGION} \
  --project=${GCP_PROJECT_ID_PROD} \
  --description="Docker images for agent-memory-graph Cloud Run service (prod)"
```

After first `terraform init`, commit the generated `.terraform.lock.hcl` file so that provider versions
are pinned for reproducible CI runs. TODO: commit `.terraform.lock.hcl` after initial bootstrap.

## GitLab CI/CD Variables

Set these in GitLab → Settings → CI/CD → Variables (project level, masked):

| Variable | Required | Example | Notes |
|---|---|---|---|
| `TF_STATE_BUCKET` | Yes | `cosmos-tf-state-prod` | GCS bucket for Terraform state; shared across products |
| `GCP_PROJECT_ID_DEV` | Yes | `my-project-dev-xxxx` | Cloud Run project, dev environment |
| `GCP_PROJECT_ID_INTG` | Yes | `my-project-intg-xxxx` | Cloud Run project, intg environment |
| `GCP_PROJECT_ID_PROD` | Yes | `my-project-prod-xxxx` | Cloud Run project, prod environment |
| `GCP_REGION` | Yes | `us-east1` | GCP region for Cloud Run and Artifact Registry |
| `GOOGLE_CREDENTIALS` | Yes | `{...}` | Service account JSON key for CI runner; must have roles listed below |
| `COMPANY_ID` | Yes | `latam-airlines` | Company identifier injected into terraform.tfvars; used for single-company auth mode |

## CI Service Account Roles

The `GOOGLE_CREDENTIALS` service account needs these roles in each project:

```
roles/run.admin
roles/iam.serviceAccountUser
roles/artifactregistry.admin
roles/spanner.admin
roles/secretmanager.admin
roles/storage.admin           # For Terraform state bucket
```

## Branch → Environment Mapping

| Git Branch | Terraform Workspace | Action |
|---|---|---|
| Any feature branch | dev | `terraform plan` only |
| `develop` | dev | `terraform plan` + `terraform apply` |
| `intg` | intg | `terraform plan` + advana workflow + `terraform apply` |
| `main` | prod | `terraform plan` + human approval + `terraform apply` |

## Adding a New Adopting Project

To deploy `agent-memory-graph` to a new team's projects:

1. Set up three GCP projects: `{team}-dev-xxxx`, `{team}-intg-xxxx`, `{team}-prod-xxxx`
2. Ensure `cosmos-cicd-sa@{project}.iam.gserviceaccount.com` exists in each project
3. Fork or copy this repo's `infrastructure/terraform/` directory
4. Update the project IDs in GitLab CI variables for the new deployment
5. Run `terraform init -backend-config="bucket={state-bucket}" && terraform workspace select dev && terraform apply`

## Manual Deployment (without CI)

```bash
cd infrastructure/terraform

# 1. Write tfvars (replace placeholders)
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with real project IDs

# 2. Initialize and select workspace
terraform init -backend-config="bucket=<TF_STATE_BUCKET>"
terraform workspace select dev   # or intg / prod

# 3. Plan and apply
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```
