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

output "audit_log_bucket_name" {
  description = "Dedicated Cloud Logging bucket for long-term audit retention."
  value       = google_logging_project_bucket_config.audit_events.name
}

output "workload_identity_provider_name" {
  description = "GitLab OIDC Workload Identity provider resource name when enabled."
  value       = var.enable_workload_identity_federation ? google_iam_workload_identity_pool_provider.gitlab_oidc[0].name : ""
}

output "monitoring_custom_service_name" {
  description = "Cloud Monitoring custom service name used for AMG SLOs."
  value       = google_monitoring_custom_service.amg.name
}

output "availability_slo_name" {
  description = "Availability SLO full resource name."
  value       = google_monitoring_slo.availability.name
}

output "latency_slo_name" {
  description = "Latency SLO full resource name."
  value       = google_monitoring_slo.latency_p95.name
}

output "error_rate_slo_name" {
  description = "Error-rate SLO full resource name."
  value       = google_monitoring_slo.error_rate.name
}

output "executive_slo_dashboard_name" {
  description = "Monitoring dashboard ID for executive SLO view."
  value       = google_monitoring_dashboard.executive_slo.id
}

output "technical_slo_dashboard_name" {
  description = "Monitoring dashboard ID for technical SLO view."
  value       = google_monitoring_dashboard.technical_slo.id
}
