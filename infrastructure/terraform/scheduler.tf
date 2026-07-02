###############################################################################
# Cloud Scheduler — automated cognitive decay and pruning
###############################################################################

locals {
  scheduler_sa_id = "amg-scheduler-sa"
}

resource "google_service_account" "scheduler_sa" {
  count = var.enable_scheduler_jobs ? 1 : 0

  account_id   = local.scheduler_sa_id
  display_name = "Agent Memory Graph Scheduler — ${local.environment}"
  description  = "OIDC caller identity for Cloud Scheduler internal maintenance jobs."
  project      = local.project_id
}

resource "google_cloud_run_v2_service_iam_member" "scheduler_sa_invoker" {
  count = var.enable_scheduler_jobs ? 1 : 0

  project  = local.project_id
  location = local.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_sa[0].email}"
}

resource "google_cloud_scheduler_job" "decay_weights" {
  count = var.enable_scheduler_jobs ? 1 : 0

  name        = "amg-decay-weights-daily"
  description = "Daily cognitive weight decay for Agent Memory Graph."
  project     = local.project_id
  region      = var.scheduler_location
  schedule    = var.scheduler_decay_schedule
  time_zone   = var.scheduler_time_zone

  http_target {
    uri         = "${google_cloud_run_v2_service.app.uri}/internal/decay-weights"
    http_method = "POST"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      decay_rate = var.scheduler_decay_rate
    }))

    oidc_token {
      service_account_email = google_service_account.scheduler_sa[0].email
      audience              = google_cloud_run_v2_service.app.uri
    }
  }

  retry_config {
    retry_count          = 2
    min_backoff_duration = "60s"
    max_backoff_duration = "3600s"
  }

  depends_on = [google_cloud_run_v2_service_iam_member.scheduler_sa_invoker]
}

resource "google_cloud_scheduler_job" "prune_weights" {
  count = var.enable_scheduler_jobs ? 1 : 0

  name        = "amg-prune-weights-weekly"
  description = "Weekly cognitive weight pruning for Agent Memory Graph."
  project     = local.project_id
  region      = var.scheduler_location
  schedule    = var.scheduler_prune_schedule
  time_zone   = var.scheduler_time_zone

  http_target {
    uri         = "${google_cloud_run_v2_service.app.uri}/internal/prune-weights"
    http_method = "POST"

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      threshold = var.scheduler_prune_threshold
    }))

    oidc_token {
      service_account_email = google_service_account.scheduler_sa[0].email
      audience              = google_cloud_run_v2_service.app.uri
    }
  }

  retry_config {
    retry_count          = 2
    min_backoff_duration = "60s"
    max_backoff_duration = "3600s"
  }

  depends_on = [google_cloud_run_v2_service_iam_member.scheduler_sa_invoker]
}

resource "google_monitoring_alert_policy" "scheduler_decay_failures" {
  count = var.enable_scheduler_jobs ? 1 : 0

  display_name          = "Agent Memory Graph — Scheduler Decay Failures (${local.environment})"
  project               = local.project_id
  combiner              = "OR"
  notification_channels = var.notification_channels

  conditions {
    display_name = "Decay scheduler failures > 0 in 15 minutes"

    condition_threshold {
      filter = <<-EOT
        metric.type="cloudscheduler.googleapis.com/job/execution_count"
        resource.type="cloud_scheduler_job"
        resource.label.job_id="${google_cloud_scheduler_job.decay_weights[0].name}"
        metric.label.status="failed"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "900s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Cloud Scheduler decay job has failures. Review Cloud Scheduler execution logs and Cloud Run endpoint `/internal/decay-weights`."
    mime_type = "text/markdown"
  }

  severity = local.environment == "prod" ? "ERROR" : "WARNING"
}

resource "google_monitoring_alert_policy" "scheduler_prune_failures" {
  count = var.enable_scheduler_jobs ? 1 : 0

  display_name          = "Agent Memory Graph — Scheduler Prune Failures (${local.environment})"
  project               = local.project_id
  combiner              = "OR"
  notification_channels = var.notification_channels

  conditions {
    display_name = "Prune scheduler failures > 0 in 15 minutes"

    condition_threshold {
      filter = <<-EOT
        metric.type="cloudscheduler.googleapis.com/job/execution_count"
        resource.type="cloud_scheduler_job"
        resource.label.job_id="${google_cloud_scheduler_job.prune_weights[0].name}"
        metric.label.status="failed"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "900s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Cloud Scheduler prune job has failures. Review Cloud Scheduler execution logs and Cloud Run endpoint `/internal/prune-weights`."
    mime_type = "text/markdown"
  }

  severity = local.environment == "prod" ? "ERROR" : "WARNING"
}

resource "google_monitoring_alert_policy" "scheduler_decay_absence" {
  count = var.enable_scheduler_jobs ? 1 : 0

  display_name          = "Agent Memory Graph - Scheduler Decay Missing Execution (${local.environment})"
  project               = local.project_id
  combiner              = "OR"
  notification_channels = var.notification_channels

  conditions {
    display_name = "Decay scheduler has no execution in expected window"

    condition_absent {
      filter = <<-EOT
        metric.type="cloudscheduler.googleapis.com/job/execution_count"
        resource.type="cloud_scheduler_job"
        resource.label.job_id="${google_cloud_scheduler_job.decay_weights[0].name}"
      EOT

      duration = var.scheduler_decay_absence_window

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Cloud Scheduler decay job has not executed in the expected window. Check Cloud Scheduler job state and Cloud Run endpoint `/internal/decay-weights`."
    mime_type = "text/markdown"
  }

  severity = local.environment == "prod" ? "ERROR" : "WARNING"
}

resource "google_monitoring_alert_policy" "scheduler_prune_absence" {
  count = var.enable_scheduler_jobs ? 1 : 0

  display_name          = "Agent Memory Graph - Scheduler Prune Missing Execution (${local.environment})"
  project               = local.project_id
  combiner              = "OR"
  notification_channels = var.notification_channels

  conditions {
    display_name = "Prune scheduler has no execution in expected window"

    condition_absent {
      filter = <<-EOT
        metric.type="cloudscheduler.googleapis.com/job/execution_count"
        resource.type="cloud_scheduler_job"
        resource.label.job_id="${google_cloud_scheduler_job.prune_weights[0].name}"
      EOT

      duration = var.scheduler_prune_absence_window

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Cloud Scheduler prune job has not executed in the expected window. Check Cloud Scheduler job state and Cloud Run endpoint `/internal/prune-weights`."
    mime_type = "text/markdown"
  }

  severity = local.environment == "prod" ? "ERROR" : "WARNING"
}