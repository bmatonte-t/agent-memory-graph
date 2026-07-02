###############################################################################
# Variables
#
# All environment-specific values are map(string) resolved at apply time via
#   lookup(var.<name>, terraform.workspace)
# This matches the Cosmos platform convention used across data products.
#
# Fill terraform.tfvars with real values before running terraform plan.
###############################################################################

# ---------------------------------------------------------------------------
# GCP project IDs
# ---------------------------------------------------------------------------

variable "project_id" {
  description = "GCP project ID per environment (dev/intg/prod) for Cloud Run."
  type        = map(string)
  default = {
    dev  = ""
    intg = ""
    prod = ""
  }
}

variable "spanner_project_id" {
  description = <<-EOT
    GCP project ID hosting the Spanner instance, per environment.
    May differ from project_id when Spanner lives in a central data project.
  EOT
  type        = map(string)
  default = {
    dev  = ""
    intg = ""
    prod = ""
  }
}

variable "region" {
  description = "GCP region for Cloud Run deployment, per environment."
  type        = map(string)
  default = {
    dev  = "us-central1"
    intg = "us-central1"
    prod = "us-central1"
  }
}

# ---------------------------------------------------------------------------
# Spanner configuration
# ---------------------------------------------------------------------------

variable "spanner_instance_id" {
  description = "Spanner instance ID per environment (instance must pre-exist)."
  type        = map(string)
  default = {
    dev  = ""
    intg = ""
    prod = ""
  }
}

# ---------------------------------------------------------------------------
# Company / tenant identifier
# ---------------------------------------------------------------------------

variable "company_id" {
  description = <<-EOT
    Organisation identifier injected as the fixed TenantId across all Spanner
    tables.  Must be a non-empty string matching the value set in
    single_company.company_id in the application config.
  EOT
  type        = string

  validation {
    condition     = length(trimspace(var.company_id)) > 0
    error_message = "company_id must be a non-empty string."
  }
}

# ---------------------------------------------------------------------------
# Auth mode
# ---------------------------------------------------------------------------

variable "auth_mode" {
  description = <<-EOT
    Authorization mode for this deployment.
    - "internal": built-in ABAC (default).
    - "external": delegates to the customer policy service at external_auth_url.
  EOT
  type        = string
  default     = "internal"

  validation {
    condition     = contains(["internal", "external"], var.auth_mode)
    error_message = "auth_mode must be 'internal' or 'external'."
  }
}

variable "external_auth_url" {
  description = <<-EOT
    URL of the customer's external governance/policy service.
    Required when auth_mode = "external".
  EOT
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# Cloud Run sizing
# ---------------------------------------------------------------------------

variable "cloud_run_min_instances" {
  description = "Minimum Cloud Run instances per environment."
  type        = map(number)
  default = {
    dev  = 1
    intg = 1
    prod = 2
  }
}

variable "cloud_run_max_instances" {
  description = "Maximum Cloud Run instances per environment."
  type        = map(number)
  default = {
    dev  = 5
    intg = 10
    prod = 20
  }
}

variable "cloud_run_cpu" {
  description = "vCPU allocation per Cloud Run instance."
  type        = string
  default     = "2"
}

variable "cloud_run_memory" {
  description = "Memory allocation per Cloud Run instance (e.g., 4Gi)."
  type        = string
  default     = "4Gi"
}

variable "container_image" {
  description = "Fully qualified container image URI for the agent-memory-graph service."
  type        = string
  # Example: us-docker.pkg.dev/<project>/services/agent-memory-graph:latest
}

# ---------------------------------------------------------------------------
# IAM
# ---------------------------------------------------------------------------

variable "cicd_sa_email" {
  description = <<-EOT
    Email of the CI/CD service account (cosmos-cicd-sa) that will receive
    iam.serviceAccountUser on the product SA so the pipeline can deploy.
    Per environment.
  EOT
  type        = map(string)
  default = {
    dev  = ""
    intg = ""
    prod = ""
  }
}

variable "agents_group_email" {
  description = <<-EOT
    Google group email whose members can impersonate the product SA
    (e.g., grp_agents_data@<customer-domain>).
  EOT
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# Labels / tags
# ---------------------------------------------------------------------------

variable "labels" {
  description = "Additional resource labels merged with product default labels."
  type        = map(string)
  default     = {}
}

variable "notification_channels" {
  description = <<-EOT
    List of Cloud Monitoring notification channel resource IDs to attach to alert policies.
    Example: ["projects/my-project/notificationChannels/12345"]
    Leave empty to receive alerts in Cloud Monitoring console only.
  EOT
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# Networking (Cloud Run private egress)
# ---------------------------------------------------------------------------

variable "vpc_connector_name" {
  description = <<-EOT
    Existing VPC Access connector name per environment to route Cloud Run egress
    through private networking (for example, to private Spanner endpoints).
    Leave empty string to disable VPC connector attachment.
  EOT
  type        = map(string)
  default = {
    dev  = ""
    intg = ""
    prod = ""
  }
}

# ---------------------------------------------------------------------------
# CI security hardening (Workload Identity Federation)
# ---------------------------------------------------------------------------

variable "enable_workload_identity_federation" {
  description = "Enable GitLab OIDC Workload Identity Federation resources."
  type        = bool
  default     = false
}

variable "gitlab_oidc_issuer_uri" {
  description = "OIDC issuer for GitLab CI (for example https://gitlab.com)."
  type        = string
  default     = "https://gitlab.com"
}

variable "gitlab_oidc_allowed_audiences" {
  description = "Allowed audiences for GitLab OIDC tokens used by CI jobs."
  type        = list(string)
  default     = []
}

variable "gitlab_project_path" {
  description = <<-EOT
    GitLab project path allowed to federate (for example group/subgroup/project).
    Used to constrain principalSet binding with attribute.project_path.
  EOT
  type        = string
  default     = ""
}

variable "workload_identity_pool_id" {
  description = "Workload Identity Pool ID for GitLab OIDC federation."
  type        = string
  default     = "gitlab-ci-pool"
}

variable "workload_identity_provider_id" {
  description = "Workload Identity Provider ID for GitLab OIDC federation."
  type        = string
  default     = "gitlab-ci-provider"
}

# ---------------------------------------------------------------------------
# Audit retention controls
# ---------------------------------------------------------------------------

variable "audit_log_retention_days" {
  description = "Retention in days for dedicated audit log bucket (2555 ~= 7 years)."
  type        = number
  default     = 2555
}

# ---------------------------------------------------------------------------
# Cloud Scheduler controls for internal maintenance jobs
# ---------------------------------------------------------------------------

variable "enable_scheduler_jobs" {
  description = "Enable Cloud Scheduler resources for decay/prune maintenance jobs."
  type        = bool
  default     = true
}

variable "scheduler_location" {
  description = "Cloud Scheduler region for maintenance jobs."
  type        = string
  default     = "us-central1"
}

variable "scheduler_time_zone" {
  description = "Timezone used for scheduler CRON evaluation."
  type        = string
  default     = "UTC"
}

variable "scheduler_decay_schedule" {
  description = "CRON schedule for temporal decay endpoint."
  type        = string
  default     = "0 2 * * *"
}

variable "scheduler_prune_schedule" {
  description = "CRON schedule for pruning endpoint."
  type        = string
  default     = "0 3 * * 0"
}

variable "scheduler_decay_rate" {
  description = "Decay rate payload sent by Cloud Scheduler."
  type        = number
  default     = 0.05

  validation {
    condition     = var.scheduler_decay_rate >= 0 && var.scheduler_decay_rate <= 1
    error_message = "scheduler_decay_rate must be between 0 and 1."
  }
}

variable "scheduler_prune_threshold" {
  description = "Pruning threshold payload sent by Cloud Scheduler."
  type        = number
  default     = 0.30

  validation {
    condition     = var.scheduler_prune_threshold >= 0 && var.scheduler_prune_threshold <= 1
    error_message = "scheduler_prune_threshold must be between 0 and 1."
  }
}

variable "scheduler_decay_absence_window" {
  description = "Monitoring window for missing decay executions (duration string, e.g. 129600s for 36h)."
  type        = string
  default     = "129600s"
}

variable "scheduler_prune_absence_window" {
  description = "Monitoring window for missing prune executions (duration string, e.g. 691200s for 8d)."
  type        = string
  default     = "691200s"
}

# ---------------------------------------------------------------------------
# SLO controls for objective-based operations
# ---------------------------------------------------------------------------

variable "monitoring_service_id" {
  description = "Service ID for Cloud Monitoring custom service hosting AMG SLOs."
  type        = string
  default     = "agent-memory-graph"
}

variable "slo_rolling_period_days" {
  description = "Rolling period in days used by all AMG SLO definitions."
  type        = number
  default     = 30

  validation {
    condition     = var.slo_rolling_period_days >= 1 && var.slo_rolling_period_days <= 30
    error_message = "slo_rolling_period_days must be between 1 and 30."
  }
}

variable "slo_target_availability" {
  description = "Availability SLO target ratio (e.g., 0.995 for 99.5%)."
  type        = number
  default     = 0.995

  validation {
    condition     = var.slo_target_availability > 0 && var.slo_target_availability < 1
    error_message = "slo_target_availability must be > 0 and < 1."
  }
}

variable "slo_target_latency" {
  description = "Latency SLO target ratio for requests under threshold (e.g., 0.95)."
  type        = number
  default     = 0.95

  validation {
    condition     = var.slo_target_latency > 0 && var.slo_target_latency < 1
    error_message = "slo_target_latency must be > 0 and < 1."
  }
}

variable "slo_target_error_rate" {
  description = "Success-ratio target for error-rate SLO (e.g., 0.99 means <=1% errors)."
  type        = number
  default     = 0.99

  validation {
    condition     = var.slo_target_error_rate > 0 && var.slo_target_error_rate < 1
    error_message = "slo_target_error_rate must be > 0 and < 1."
  }
}

variable "slo_latency_threshold_ms" {
  description = "Latency threshold in milliseconds for the latency SLO distribution cut."
  type        = number
  default     = 500

  validation {
    condition     = var.slo_latency_threshold_ms > 0
    error_message = "slo_latency_threshold_ms must be > 0."
  }
}

variable "slo_burn_rate_short_threshold" {
  description = "Short-window burn-rate threshold for SLO alerting."
  type        = number
  default     = 14

  validation {
    condition     = var.slo_burn_rate_short_threshold > 0
    error_message = "slo_burn_rate_short_threshold must be > 0."
  }
}

variable "slo_burn_rate_long_threshold" {
  description = "Long-window burn-rate threshold for SLO alerting."
  type        = number
  default     = 6

  validation {
    condition     = var.slo_burn_rate_long_threshold > 0
    error_message = "slo_burn_rate_long_threshold must be > 0."
  }
}

variable "slo_burn_rate_short_window" {
  description = "Short burn-rate observation window (duration string, e.g. 300s)."
  type        = string
  default     = "300s"
}

variable "slo_burn_rate_long_window" {
  description = "Long burn-rate observation window (duration string, e.g. 3600s)."
  type        = string
  default     = "3600s"
}
