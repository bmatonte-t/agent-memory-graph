###############################################################################
# Spanner — database and cross-project IAM
#
# The Spanner instance is assumed to pre-exist (managed by the central data
# platform team).  We create only the database and run schema migrations via
# a null_resource provisioner.
###############################################################################

locals {
  spanner_instance_id  = lookup(var.spanner_instance_id, local.environment)
  spanner_database_id  = "agent-memory-graph-${local.environment}"
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
    google_service_account.spanner_sa,
    google_project_iam_member.spanner_sa_database_role,
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
  # Re-run whenever the list of migration files changes
  triggers = {
    migrations_hash = sha256(join(",", [
      for f in sort(fileset("${path.module}/../../migrations", "*.sql")) : f
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
