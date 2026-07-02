###############################################################################
# Spanner — instance, database, and cross-project IAM
#
# We provision the Spanner instance directly so Terraform owns the full
# lifecycle.  Processing units are set to the minimum (100) for dev/intg and
# doubled (200) for prod; raise when load warrants it.
###############################################################################

locals {
  spanner_instance_id  = lookup(var.spanner_instance_id, local.environment)
  spanner_database_id  = "agent-memory-graph-${local.environment}"
  spanner_instance_config = "regional-${local.region}"
}

###############################################################################
# Spanner instance
#
# Provisory names: agent-memory-graph-{env}
# Processing units default to 100 (minimum, ~1/10 of 1000-PU node).
# Increase processing_units in prod when load warrants it.
###############################################################################

resource "google_spanner_instance" "main" {
  project          = local.spanner_project_id
  name             = local.spanner_instance_id
  display_name     = "Agent Memory Graph (${local.environment})"
  config           = local.spanner_instance_config
  processing_units = local.environment == "prod" ? 200 : 100

  labels = local.common_labels
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

resource "google_spanner_database" "memory_graph" {
  project  = local.spanner_project_id
  instance = local.spanner_instance_id
  name     = local.spanner_database_id

  # Deletion protection — disabled only in dev so we can rebuild cleanly
  deletion_protection = local.environment != "dev"

  # Database-level IAM binding: only the Spanner SA can access this DB.
  # Project-level roles are kept narrow; per-DB binding is tighter.
  depends_on = [
    google_spanner_instance.main,
    google_service_account.spanner_sa,
  ]
}

# Database-level IAM: restrict access to the dedicated Spanner SA only
resource "google_spanner_database_iam_member" "spanner_sa_user" {
  project  = local.spanner_project_id
  instance = local.spanner_instance_id
  database = google_spanner_database.memory_graph.name
  role     = "roles/spanner.databaseUser"
  member   = "serviceAccount:${google_service_account.spanner_sa.email}"
}

# ---------------------------------------------------------------------------
# Schema migrations
#
# Migrations are SQL files in the repo's migrations/ directory.
# The null_resource runs them in order on every apply (idempotent SQL DDL).
# Cloud SDK (gcloud) must be available in the CI runner image.
# ---------------------------------------------------------------------------

resource "null_resource" "run_migrations" {
  # Re-run whenever the list or content of migration files changes
  triggers = {
    migrations_hash = sha256(join(",", [
      for f in sort(fileset("${path.module}/../../migrations", "*.sql")) :
      "${f}:${filesha256("${path.module}/../../migrations/${f}")}"
    ]))
    database = google_spanner_database.memory_graph.name
  }

  provisioner "local-exec" {
    command = <<-SCRIPT
      set -euo pipefail
      MIGRATIONS_DIR="${path.module}/../../migrations"
      for sql_file in $(ls "$MIGRATIONS_DIR"/*.sql | sort); do
        echo "Applying migration: $sql_file"
        gcloud spanner databases ddl update "${local.spanner_database_id}" \
          --instance="${local.spanner_instance_id}" \
          --project="${local.spanner_project_id}" \
          --ddl-file="$sql_file"
      done
      echo "All migrations applied."
    SCRIPT
    interpreter = ["bash", "-c"]
  }

  depends_on = [google_spanner_database.memory_graph]
}
