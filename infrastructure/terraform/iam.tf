###############################################################################
# IAM — Service accounts and role bindings
#
# Three SAs follow the Cosmos least-privilege pattern:
#   1. agent-memory-graph-sa     – runs Cloud Run, writes logs, accesses secrets
#   2. agent-memory-graph-spanner-sa – cross-project Spanner access only
#   3. cosmos-cicd-sa (pre-existing) – deploy permission on the product SA
###############################################################################

locals {
  product_sa_id  = "agent-memory-graph-sa"
  spanner_sa_id  = "agent-memory-graph-spanner-sa"
  product_sa_email = "${local.product_sa_id}@${local.project_id}.iam.gserviceaccount.com"
  spanner_sa_email = "${local.spanner_sa_id}@${local.spanner_project_id}.iam.gserviceaccount.com"
}

# ---------------------------------------------------------------------------
# Product service account (Cloud Run identity)
# ---------------------------------------------------------------------------

resource "google_service_account" "product_sa" {
  account_id   = local.product_sa_id
  display_name = "Agent Memory Graph — ${local.environment}"
  description  = "Runtime identity for agent-memory-graph Cloud Run service."
  project      = local.project_id
}

# Roles granted on the Cloud Run project
resource "google_project_iam_member" "product_sa_roles" {
  for_each = toset([
    "roles/run.invoker",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/monitoring.metricWriter",
    "roles/secretmanager.secretAccessor",
  ])

  project = local.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.product_sa.email}"
}

# Allow the CICD SA to act as the product SA for deployments
resource "google_service_account_iam_member" "cicd_sa_user" {
  count              = lookup(var.cicd_sa_email, local.environment, "") != "" ? 1 : 0
  service_account_id = google_service_account.product_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${lookup(var.cicd_sa_email, local.environment)}"
}

# Allow an agent group to impersonate the product SA (optional)
resource "google_service_account_iam_member" "agents_group_impersonation" {
  count              = var.agents_group_email != "" ? 1 : 0
  service_account_id = google_service_account.product_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "group:${var.agents_group_email}"
}

# ---------------------------------------------------------------------------
# Spanner service account (cross-project access)
#
# Created in the Spanner project so its binding on the Spanner DB is
# project-local, keeping IAM blast radius tight.
# ---------------------------------------------------------------------------

resource "google_service_account" "spanner_sa" {
  account_id   = local.spanner_sa_id
  display_name = "Agent Memory Graph Spanner — ${local.environment}"
  description  = "Cross-project Spanner access for agent-memory-graph."
  project      = local.spanner_project_id
}

# Grant Spanner data read/write in the Spanner project
resource "google_project_iam_member" "spanner_sa_database_role" {
  project = local.spanner_project_id
  role    = "roles/spanner.databaseUser"
  member  = "serviceAccount:${google_service_account.spanner_sa.email}"
}

# Let the product SA impersonate the Spanner SA for cross-project calls
resource "google_service_account_iam_member" "product_sa_impersonates_spanner_sa" {
  service_account_id = google_service_account.spanner_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.product_sa.email}"
}

# Allow the product SA to generate Spanner credentials via the Spanner SA
resource "google_service_account_iam_member" "product_sa_is_spanner_sa_user" {
  service_account_id = google_service_account.spanner_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.product_sa.email}"
}
