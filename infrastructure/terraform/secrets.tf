###############################################################################
# Secrets — Secret Manager resources
#
# All credentials are stored in Secret Manager scoped to the product SA.
# Secrets are named: agent-memory-graph-{resource}-{credential-type}
# This follows the Cosmos naming convention.
###############################################################################

# ---------------------------------------------------------------------------
# Spanner SA key
#
# Used by the Cloud Run service to access Spanner in the cross-project pattern.
# The key is generated here and stored in Secret Manager; the SA key rotation
# should be automated via Cloud Scheduler in a production hardening pass.
# ---------------------------------------------------------------------------

resource "google_service_account_key" "spanner_sa_key" {
  service_account_id = google_service_account.spanner_sa.name
  public_key_type    = "TYPE_X509_PEM_FILE"
}

resource "google_secret_manager_secret" "spanner_credentials" {
  project   = local.project_id
  secret_id = "agent-memory-graph-spanner-credentials"
  labels    = local.common_labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "spanner_credentials_version" {
  secret      = google_secret_manager_secret.spanner_credentials.id
  secret_data = base64decode(google_service_account_key.spanner_sa_key.private_key)
}

resource "google_secret_manager_secret_iam_member" "product_sa_reads_spanner_creds" {
  project   = local.project_id
  secret_id = google_secret_manager_secret.spanner_credentials.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.product_sa.email}"
}

# ---------------------------------------------------------------------------
# Application config blob
#
# The full config.yaml content is stored as a secret so it can be mounted
# into Cloud Run without baking it into the container image.
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "app_config" {
  project   = local.project_id
  secret_id = "agent-memory-graph-config"
  labels    = local.common_labels

  replication {
    auto {}
  }
}

# The config template is rendered from a local file; sensitive values (SA keys,
# URLs) are substituted at apply time.
resource "google_secret_manager_secret_version" "app_config_version" {
  secret = google_secret_manager_secret.app_config.id

  secret_data = templatefile("${path.module}/templates/config.yaml.tpl", {
    company_id         = var.company_id
    auth_mode          = var.auth_mode
    external_auth_url  = var.external_auth_url
    environment        = local.environment
    spanner_project_id = local.spanner_project_id
    spanner_instance   = local.spanner_instance_id
    spanner_database   = local.spanner_database_id
  })
}

resource "google_secret_manager_secret_iam_member" "product_sa_reads_config" {
  project   = local.project_id
  secret_id = google_secret_manager_secret.app_config.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.product_sa.email}"
}

# ---------------------------------------------------------------------------
# External auth URL (conditional — only when auth_mode = "external")
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "external_auth_url" {
  count     = var.auth_mode == "external" ? 1 : 0
  project   = local.project_id
  secret_id = "agent-memory-graph-external-auth-url"
  labels    = local.common_labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "external_auth_url_version" {
  count       = var.auth_mode == "external" ? 1 : 0
  secret      = google_secret_manager_secret.external_auth_url[0].id
  secret_data = var.external_auth_url
}

resource "google_secret_manager_secret_iam_member" "product_sa_reads_auth_url" {
  count     = var.auth_mode == "external" ? 1 : 0
  project   = local.project_id
  secret_id = google_secret_manager_secret.external_auth_url[0].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.product_sa.email}"
}
