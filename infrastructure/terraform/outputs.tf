###############################################################################
# Outputs — values used by CI/CD, runbooks, and downstream tooling
###############################################################################

output "cloud_run_url" {
  description = "HTTPS URL of the deployed agent-memory-graph Cloud Run service."
  value       = google_cloud_run_v2_service.app.uri
}

output "cloud_run_service_name" {
  description = "Cloud Run service name."
  value       = google_cloud_run_v2_service.app.name
}

output "product_sa_email" {
  description = "Email of the Cloud Run product service account."
  value       = google_service_account.product_sa.email
}

output "spanner_sa_email" {
  description = "Email of the dedicated Spanner service account."
  value       = google_service_account.spanner_sa.email
}

output "spanner_database_path" {
  description = "Full Spanner database path for use in application config."
  value       = "projects/${local.spanner_project_id}/instances/${local.spanner_instance_id}/databases/${local.spanner_database_id}"
}

output "spanner_credentials_secret_name" {
  description = "Secret Manager resource name for the Spanner SA credentials."
  value       = google_secret_manager_secret.spanner_credentials.name
}

output "app_config_secret_name" {
  description = "Secret Manager resource name for the application config blob."
  value       = google_secret_manager_secret.app_config.name
}

output "environment" {
  description = "Active Terraform workspace / environment."
  value       = local.environment
}
