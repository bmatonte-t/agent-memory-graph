###############################################################################
# Monitoring — log-based metrics and alert policies
###############################################################################

# ---------------------------------------------------------------------------
# Log-based metrics
# ---------------------------------------------------------------------------

resource "google_logging_metric" "request_latency" {
  name        = "agent-memory-graph/request-latency"
  description = "Latency distribution of MCP tool invocations (ms)."
  project     = local.project_id

  filter = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${local.service_name}"
    jsonPayload.latency_ms!=""
  EOT

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "DISTRIBUTION"
    unit         = "ms"
    display_name = "Agent Memory Graph — Request Latency"
  }

  value_extractor = "EXTRACT(jsonPayload.latency_ms)"

  bucket_options {
    explicit_buckets {
      # Latency histogram: 0–50–100–200–500–1000–5000ms
      bounds = [0, 50, 100, 200, 500, 1000, 5000]
    }
  }

  label_extractors = {
    tool_name = "EXTRACT(jsonPayload.tool_name)"
  }
}

resource "google_logging_metric" "error_count" {
  name        = "agent-memory-graph/error-count"
  description = "Count of MCP tool invocation errors by tool name."
  project     = local.project_id

  filter = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${local.service_name}"
    jsonPayload.success=false
  EOT

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    display_name = "Agent Memory Graph — Error Count"
    labels {
      key         = "tool_name"
      value_type  = "STRING"
      description = "MCP tool name that produced the error."
    }
    labels {
      key         = "error_code"
      value_type  = "STRING"
      description = "Application error code."
    }
  }

  label_extractors = {
    tool_name  = "EXTRACT(jsonPayload.tool_name)"
    error_code = "EXTRACT(jsonPayload.error_code)"
  }
}

# ---------------------------------------------------------------------------
# Alert policies
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name          = "Agent Memory Graph — High Error Rate (${local.environment})"
  project               = local.project_id
  combiner              = "OR"
  notification_channels = var.notification_channels

  conditions {
    display_name = "Error rate > 1% for 5 minutes"

    condition_threshold {
      filter = <<-EOT
        metric.type="logging.googleapis.com/user/agent-memory-graph/error-count"
        resource.type="cloud_run_revision"
      EOT

      comparison = "COMPARISON_GT"
      threshold_value = 0.01
      duration        = "300s"  # 5 minutes

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"  # Auto-close after 30 minutes if resolved
  }

  documentation {
    content   = "MCP tool error rate exceeded 1% sustained over 5 minutes. Check Cloud Run logs for root cause."
    mime_type = "text/markdown"
  }

  # Only page on-call in prod; other environments create tickets only
  severity = local.environment == "prod" ? "ERROR" : "WARNING"
}

resource "google_monitoring_alert_policy" "high_latency" {
  display_name          = "Agent Memory Graph — High Latency p99 (${local.environment})"
  project               = local.project_id
  combiner              = "OR"
  notification_channels = var.notification_channels

  conditions {
    display_name = "p99 request latency > 500ms for 10 minutes"

    condition_threshold {
      filter = <<-EOT
        metric.type="logging.googleapis.com/user/agent-memory-graph/request-latency"
        resource.type="cloud_run_revision"
      EOT

      comparison = "COMPARISON_GT"
      threshold_value = 500
      duration        = "600s"  # 10 minutes

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_PERCENTILE_99"
        cross_series_reducer = "REDUCE_MEAN"
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
    content   = "Request latency p99 exceeded 500ms. Check Spanner contention, Cloud Run scaling, and query plans."
    mime_type = "text/markdown"
  }

  severity = local.environment == "prod" ? "ERROR" : "WARNING"
}
