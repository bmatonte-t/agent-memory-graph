###############################################################################
# Monitoring — log-based metrics and alert policies
###############################################################################

resource "google_monitoring_custom_service" "amg" {
  service_id   = var.monitoring_service_id
  display_name = "Agent Memory Graph (${local.environment})"
  project      = local.project_id
}

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

resource "google_logging_metric" "mcp_invocation_count" {
  name        = "agent-memory-graph/mcp-invocation-count"
  description = "Total MCP tool invocations with success label for SLO/error-budget math."
  project     = local.project_id

  filter = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${local.service_name}"
    jsonPayload.event="mcp_tool_invoke_finish"
  EOT

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    display_name = "Agent Memory Graph — MCP Invocation Count"
    labels {
      key         = "tool_name"
      value_type  = "STRING"
      description = "MCP tool name."
    }
    labels {
      key         = "success"
      value_type  = "STRING"
      description = "Invocation success flag from application logs."
    }
  }

  label_extractors = {
    tool_name = "EXTRACT(jsonPayload.tool_name)"
    success   = "EXTRACT(jsonPayload.success)"
  }
}

# ---------------------------------------------------------------------------
# SLOs
# ---------------------------------------------------------------------------

resource "google_monitoring_slo" "availability" {
  service      = google_monitoring_custom_service.amg.name
  slo_id       = "availability-995"
  display_name = "Availability SLO 99.5% (${local.environment})"
  goal         = var.slo_target_availability

  rolling_period_days = var.slo_rolling_period_days

  request_based_sli {
    good_total_ratio {
      total_service_filter = <<-EOT
        metric.type="run.googleapis.com/request_count"
        resource.type="cloud_run_revision"
        resource.label.service_name="${local.service_name}"
      EOT
      good_service_filter  = <<-EOT
        metric.type="run.googleapis.com/request_count"
        resource.type="cloud_run_revision"
        resource.label.service_name="${local.service_name}"
        metric.label.response_code_class!="5xx"
      EOT
    }
  }
}

resource "google_monitoring_slo" "latency_p95" {
  service      = google_monitoring_custom_service.amg.name
  slo_id       = "latency-p95"
  display_name = "Latency SLO p95 <= 500ms (${local.environment})"
  goal         = var.slo_target_latency

  rolling_period_days = var.slo_rolling_period_days

  request_based_sli {
    distribution_cut {
      distribution_filter = <<-EOT
        metric.type="logging.googleapis.com/user/agent-memory-graph/request-latency"
        resource.type="cloud_run_revision"
        resource.label.service_name="${local.service_name}"
      EOT
      range {
        min = 0
        max = var.slo_latency_threshold_ms
      }
    }
  }
}

resource "google_monitoring_slo" "error_rate" {
  service      = google_monitoring_custom_service.amg.name
  slo_id       = "error-rate"
  display_name = "Error-rate SLO (>=99.0% success) (${local.environment})"
  goal         = var.slo_target_error_rate

  rolling_period_days = var.slo_rolling_period_days

  request_based_sli {
    good_total_ratio {
      total_service_filter = <<-EOT
        metric.type="logging.googleapis.com/user/agent-memory-graph/mcp-invocation-count"
        resource.type="cloud_run_revision"
        resource.label.service_name="${local.service_name}"
      EOT
      good_service_filter  = <<-EOT
        metric.type="logging.googleapis.com/user/agent-memory-graph/mcp-invocation-count"
        resource.type="cloud_run_revision"
        resource.label.service_name="${local.service_name}"
        metric.label.success="true"
      EOT
    }
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

      comparison      = "COMPARISON_GT"
      threshold_value = 0.01
      duration        = "300s" # 5 minutes

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
    auto_close = "1800s" # Auto-close after 30 minutes if resolved
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

      comparison      = "COMPARISON_GT"
      threshold_value = 500
      duration        = "600s" # 10 minutes

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

resource "google_monitoring_alert_policy" "high_authorization_denial_rate" {
  display_name          = "Agent Memory Graph — High Authorization Denial Rate (${local.environment})"
  project               = local.project_id
  combiner              = "OR"
  notification_channels = var.notification_channels

  conditions {
    display_name = "Authorization denial rate > 10/min"

    condition_threshold {
      filter          = "metric.type=\"custom.googleapis.com/authorization.denied\""
      comparison      = "COMPARISON_GT"
      threshold_value = 10
      duration        = "60s"

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
    auto_close = "1800s"
  }

  documentation {
    content   = "Authorization denial rate exceeded 10 denials/min. This may indicate a misconfigured agent scope or an attempted privilege escalation. Check Cloud Run logs for AUTHZ_DENY events."
    mime_type = "text/markdown"
  }

  severity = local.environment == "prod" ? "ERROR" : "WARNING"
}

resource "google_monitoring_alert_policy" "spanner_api_p99_latency" {
  display_name          = "Agent Memory Graph — Spanner API Latency p99 (${local.environment})"
  project               = local.project_id
  combiner              = "OR"
  notification_channels = var.notification_channels

  conditions {
    display_name = "Spanner p99 API latency > 200ms for 10 minutes"

    condition_threshold {
      filter = <<-EOT
        metric.type="spanner.googleapis.com/api/request_latencies"
        resource.type="spanner_instance"
        resource.labels.project_id="${local.spanner_project_id}"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = 200
      duration        = "600s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_PERCENTILE_99"
        cross_series_reducer = "REDUCE_MAX"
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
    content   = "Spanner API request latency exceeded 200 ms p99 for 10 minutes. Review hot partitions, query plans, and connection pressure from Cloud Run."
    mime_type = "text/markdown"
  }

  severity = local.environment == "prod" ? "ERROR" : "WARNING"
}

resource "google_monitoring_alert_policy" "availability_burn_rate" {
  display_name          = "Agent Memory Graph — Availability Burn Rate (${local.environment})"
  project               = local.project_id
  combiner              = "OR"
  notification_channels = var.notification_channels

  conditions {
    display_name = "Availability burn rate short window"

    condition_threshold {
      filter = <<-EOT
        metric.type="monitoring.googleapis.com/slo/burn_rate"
        resource.type="monitoring_slo"
        resource.label.service_id="${var.monitoring_service_id}"
        resource.label.slo_id="${google_monitoring_slo.availability.slo_id}"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = var.slo_burn_rate_short_threshold
      duration        = var.slo_burn_rate_short_window

      aggregations {
        alignment_period   = var.slo_burn_rate_short_window
        per_series_aligner = "ALIGN_MEAN"
      }

      trigger {
        count = 1
      }
    }
  }

  conditions {
    display_name = "Availability burn rate long window"

    condition_threshold {
      filter = <<-EOT
        metric.type="monitoring.googleapis.com/slo/burn_rate"
        resource.type="monitoring_slo"
        resource.label.service_id="${var.monitoring_service_id}"
        resource.label.slo_id="${google_monitoring_slo.availability.slo_id}"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = var.slo_burn_rate_long_threshold
      duration        = var.slo_burn_rate_long_window

      aggregations {
        alignment_period   = var.slo_burn_rate_long_window
        per_series_aligner = "ALIGN_MEAN"
      }

      trigger {
        count = 1
      }
    }
  }

  documentation {
    content   = "Availability error budget burn rate exceeded threshold. Follow SLO incident protocol and review Cloud Run 5xx + dependency health."
    mime_type = "text/markdown"
  }

  severity = local.environment == "prod" ? "ERROR" : "WARNING"
}

resource "google_monitoring_alert_policy" "latency_burn_rate" {
  display_name          = "Agent Memory Graph — Latency Burn Rate (${local.environment})"
  project               = local.project_id
  combiner              = "OR"
  notification_channels = var.notification_channels

  conditions {
    display_name = "Latency burn rate short window"

    condition_threshold {
      filter = <<-EOT
        metric.type="monitoring.googleapis.com/slo/burn_rate"
        resource.type="monitoring_slo"
        resource.label.service_id="${var.monitoring_service_id}"
        resource.label.slo_id="${google_monitoring_slo.latency_p95.slo_id}"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = var.slo_burn_rate_short_threshold
      duration        = var.slo_burn_rate_short_window

      aggregations {
        alignment_period   = var.slo_burn_rate_short_window
        per_series_aligner = "ALIGN_MEAN"
      }

      trigger {
        count = 1
      }
    }
  }

  conditions {
    display_name = "Latency burn rate long window"

    condition_threshold {
      filter = <<-EOT
        metric.type="monitoring.googleapis.com/slo/burn_rate"
        resource.type="monitoring_slo"
        resource.label.service_id="${var.monitoring_service_id}"
        resource.label.slo_id="${google_monitoring_slo.latency_p95.slo_id}"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = var.slo_burn_rate_long_threshold
      duration        = var.slo_burn_rate_long_window

      aggregations {
        alignment_period   = var.slo_burn_rate_long_window
        per_series_aligner = "ALIGN_MEAN"
      }

      trigger {
        count = 1
      }
    }
  }

  documentation {
    content   = "Latency SLO error budget burn rate exceeded threshold. Investigate p95 regressions in MCP operations and Spanner latency hotspots."
    mime_type = "text/markdown"
  }

  severity = local.environment == "prod" ? "ERROR" : "WARNING"
}

resource "google_monitoring_alert_policy" "error_rate_burn_rate" {
  display_name          = "Agent Memory Graph — Error Rate Burn Rate (${local.environment})"
  project               = local.project_id
  combiner              = "OR"
  notification_channels = var.notification_channels

  conditions {
    display_name = "Error-rate burn rate short window"

    condition_threshold {
      filter = <<-EOT
        metric.type="monitoring.googleapis.com/slo/burn_rate"
        resource.type="monitoring_slo"
        resource.label.service_id="${var.monitoring_service_id}"
        resource.label.slo_id="${google_monitoring_slo.error_rate.slo_id}"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = var.slo_burn_rate_short_threshold
      duration        = var.slo_burn_rate_short_window

      aggregations {
        alignment_period   = var.slo_burn_rate_short_window
        per_series_aligner = "ALIGN_MEAN"
      }

      trigger {
        count = 1
      }
    }
  }

  conditions {
    display_name = "Error-rate burn rate long window"

    condition_threshold {
      filter = <<-EOT
        metric.type="monitoring.googleapis.com/slo/burn_rate"
        resource.type="monitoring_slo"
        resource.label.service_id="${var.monitoring_service_id}"
        resource.label.slo_id="${google_monitoring_slo.error_rate.slo_id}"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = var.slo_burn_rate_long_threshold
      duration        = var.slo_burn_rate_long_window

      aggregations {
        alignment_period   = var.slo_burn_rate_long_window
        per_series_aligner = "ALIGN_MEAN"
      }

      trigger {
        count = 1
      }
    }
  }

  documentation {
    content   = "Error-rate SLO burn rate exceeded threshold. Investigate failing MCP tools, error codes, and recent deploy/regression signals."
    mime_type = "text/markdown"
  }

  severity = local.environment == "prod" ? "ERROR" : "WARNING"
}

# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------

resource "google_monitoring_dashboard" "executive_slo" {
  project = local.project_id

  dashboard_json = jsonencode({
    displayName = "AMG Executive SLO Dashboard (${local.environment})"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          xPos   = 0
          yPos   = 0
          width  = 4
          height = 4
          widget = {
            title = "Availability SLO Goal"
            scorecard = {
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"monitoring.googleapis.com/slo/goal\" resource.type=\"monitoring_slo\" resource.label.slo_id=\"${google_monitoring_slo.availability.slo_id}\""
                }
              }
            }
          }
        },
        {
          xPos   = 4
          yPos   = 0
          width  = 4
          height = 4
          widget = {
            title = "Latency SLO Goal"
            scorecard = {
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"monitoring.googleapis.com/slo/goal\" resource.type=\"monitoring_slo\" resource.label.slo_id=\"${google_monitoring_slo.latency_p95.slo_id}\""
                }
              }
            }
          }
        },
        {
          xPos   = 8
          yPos   = 0
          width  = 4
          height = 4
          widget = {
            title = "Error-rate SLO Goal"
            scorecard = {
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"monitoring.googleapis.com/slo/goal\" resource.type=\"monitoring_slo\" resource.label.slo_id=\"${google_monitoring_slo.error_rate.slo_id}\""
                }
              }
            }
          }
        }
      ]
    }
  })
}

resource "google_monitoring_dashboard" "technical_slo" {
  project = local.project_id

  dashboard_json = jsonencode({
    displayName = "AMG Technical SLO Dashboard (${local.environment})"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          xPos   = 0
          yPos   = 0
          width  = 12
          height = 4
          widget = {
            title = "Cloud Run Request Count"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.label.service_name=\"${local.service_name}\""
                    }
                  }
                  plotType = "LINE"
                }
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "req/s"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 0
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "MCP Error Count"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/agent-memory-graph/error-count\" resource.type=\"cloud_run_revision\""
                    }
                  }
                  plotType = "STACKED_BAR"
                }
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "errors"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "MCP p95 Latency"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/agent-memory-graph/request-latency\" resource.type=\"cloud_run_revision\""
                      aggregation = {
                        perSeriesAligner = "ALIGN_PERCENTILE_95"
                        alignmentPeriod  = "60s"
                      }
                    }
                  }
                  plotType = "LINE"
                }
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "ms"
                scale = "LINEAR"
              }
            }
          }
        }
      ]
    }
  })
}

resource "google_logging_project_bucket_config" "audit_events" {
  project        = local.project_id
  location       = "global"
  retention_days = var.audit_log_retention_days
  bucket_id      = "agent-memory-graph-audit-events"
  description    = "Dedicated audit log bucket with long-term retention for governance controls."
}

resource "google_logging_project_sink" "audit_events" {
  project                = local.project_id
  name                   = "agent-memory-graph-audit-events"
  destination            = "logging.googleapis.com/projects/${local.project_id}/locations/global/buckets/${google_logging_project_bucket_config.audit_events.bucket_id}"
  unique_writer_identity = true

  filter = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${local.service_name}"
    (jsonPayload.event="record_audit_event_completed" OR
     jsonPayload.event="mcp_tool_invoke_finish")
  EOT
}

resource "google_project_iam_member" "audit_sink_bucket_writer" {
  project = local.project_id
  role    = "roles/logging.bucketWriter"
  member  = google_logging_project_sink.audit_events.writer_identity
}
