###############################################################################
# Artifact Registry — Docker repository for container images
#
# One repository per environment (one per GCP project / workspace).
# Repository ID: agent-memory-graph
# Images path:   {region}-docker.pkg.dev/{project_id}/agent-memory-graph/api:{tag}
###############################################################################

resource "google_artifact_registry_repository" "images" {
  project       = local.project_id
  location      = local.region
  repository_id = "agent-memory-graph"
  description   = "Docker images for agent-memory-graph Cloud Run service (${local.environment})"
  format        = "DOCKER"

  labels = local.common_labels

  cleanup_policies {
    id     = "keep-recent-5"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }

  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state = "UNTAGGED"
    }
  }
}

# Allow the product SA to pull images from the registry
resource "google_artifact_registry_repository_iam_member" "product_sa_reader" {
  project    = local.project_id
  location   = local.region
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.product_sa.email}"
}

# Allow the CICD SA to push images
resource "google_artifact_registry_repository_iam_member" "cicd_sa_writer" {
  count      = lookup(var.cicd_sa_email, local.environment, "") != "" ? 1 : 0
  project    = local.project_id
  location   = local.region
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${lookup(var.cicd_sa_email, local.environment)}"
}

# Output the full repository path for use in CI/CD
output "artifact_registry_url" {
  description = "Base URL for Docker images: {this}/{image-name}:{tag}"
  value       = "${local.region}-docker.pkg.dev/${local.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
