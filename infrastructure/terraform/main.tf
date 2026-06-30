###############################################################################
# Cloud Run service — main application deployment
###############################################################################

locals {
  service_name = "agent-memory-graph"
  min_instances = lookup(var.cloud_run_min_instances, local.environment, 1)
  max_instances = lookup(var.cloud_run_max_instances, local.environment, 20)
}

resource "google_cloud_run_v2_service" "app" {
  name     = local.service_name
  location = local.region
  project  = local.project_id

  labels = local.common_labels

  template {
    service_account = google_service_account.product_sa.email

    labels = local.common_labels

    scaling {
      min_instance_count = local.min_instances
      max_instance_count = local.max_instances
    }

    containers {
      image = var.container_image

      resources {
        limits = {
          cpu    = var.cloud_run_cpu
          memory = var.cloud_run_memory
        }
        # CPU is always allocated (not throttled when idle) for low-latency
        # memory retrieval; cost is justified at enterprise scale.
        cpu_idle = false
      }

      # -----------------------------------------------------------------------
      # Environment variables from Secret Manager
      # Secrets are referenced by version "latest" so new versions take effect
      # on the next deployment without re-running Terraform.
      # -----------------------------------------------------------------------

      env {
        name = "AGENT_MEMORY_GRAPH_ENVIRONMENT"
        value = local.environment
      }

      env {
        name = "AGENT_MEMORY_GRAPH_SINGLE_COMPANY__ENABLED"
        value = "true"
      }

      env {
        name = "AGENT_MEMORY_GRAPH_SINGLE_COMPANY__COMPANY_ID"
        value = var.company_id
      }

      env {
        name = "AGENT_MEMORY_GRAPH_SINGLE_COMPANY__AUTH_MODE"
        value = var.auth_mode
      }

      env {
        name  = "AGENT_MEMORY_GRAPH_SPANNER_PROJECT_ID"
        value = local.spanner_project_id
      }

      env {
        name  = "AGENT_MEMORY_GRAPH_SPANNER_INSTANCE_ID"
        value = local.spanner_instance_id
      }

      env {
        name  = "AGENT_MEMORY_GRAPH_SPANNER_DATABASE_ID"
        value = local.spanner_database_id
      }

      # Spanner credentials injected from Secret Manager
      volume_mounts {
        name       = "spanner-creds"
        mount_path = "/secrets/spanner"
      }

      # Application config injected from Secret Manager
      volume_mounts {
        name       = "app-config"
        mount_path = "/secrets/config"
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 10
        period_seconds        = 30
        failure_threshold     = 3
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 6
      }

      ports {
        container_port = 8080
      }
    }

    volumes {
      name = "spanner-creds"
      secret {
        secret = google_secret_manager_secret.spanner_credentials.secret_id
        items {
          version = "latest"
          path    = "key.json"
          mode    = 0
        }
      }
    }

    volumes {
      name = "app-config"
      secret {
        secret = google_secret_manager_secret.app_config.secret_id
        items {
          version = "latest"
          path    = "config.yaml"
          mode    = 0
        }
      }
    }
  }

  depends_on = [
    google_service_account.product_sa,
    google_project_iam_member.product_sa_roles,
    google_secret_manager_secret_version.spanner_credentials_version,
    google_secret_manager_secret_version.app_config_version,
    null_resource.run_migrations,
  ]
}

# roles/run.invoker scoped to this service only (not project-wide)
resource "google_cloud_run_v2_service_iam_member" "product_sa_invoker" {
  project  = local.project_id
  location = local.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.product_sa.email}"
}
