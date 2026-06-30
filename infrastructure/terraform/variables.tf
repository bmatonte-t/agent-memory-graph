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
  type = string

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
  type    = string
  default = "internal"

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
  type    = string
  default = ""
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
  type = map(string)
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
  type    = string
  default = ""
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
  type    = list(string)
  default = []
}
