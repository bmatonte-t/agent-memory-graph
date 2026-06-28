###############################################################################
# Backend & provider configuration
#
# State is stored in GCS, bucket supplied via -backend-config at CI time
# (consistent with the client's Cosmos platform pattern where the bucket is
# a shared infrastructure concern, not pinned in code).
#
# Usage:
#   terraform init -backend-config="bucket=<your-state-bucket>"
#   terraform workspace select dev   # or intg / prod
###############################################################################

terraform {
  required_version = ">= 1.5"

  backend "gcs" {
    prefix = "agent-memory-graph/state"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
}

###############################################################################
# Providers
#
# The active workspace resolves the correct project_id so every resource lands
# in the right environment without separate variable files.
###############################################################################

locals {
  # Environment derived from the active workspace: dev | intg | prod
  environment = terraform.workspace

  # Cloud Run project (where the service runs)
  project_id = lookup(var.project_id, local.environment)

  # Spanner may live in a central data project separate from Cloud Run
  spanner_project_id = lookup(var.spanner_project_id, local.environment)

  # Region for Cloud Run deployment
  region = lookup(var.region, local.environment, "us-central1")

  # Common labels applied to every resource
  common_labels = merge(var.labels, {
    product     = "agent-memory-graph"
    environment = local.environment
    managed_by  = "terraform"
  })
}

provider "google" {
  project = local.project_id
  region  = local.region
}

provider "google-beta" {
  project = local.project_id
  region  = local.region
}
