#!/usr/bin/env bash
# E7-exec Observability Deployment Script
# Deploys Cloud Logging sinks, Trace sampling, and Monitoring dashboards.
# Usage: ./scripts/deploy_observability.sh [--dry-run]
# Must run AFTER validate_infrastructure.sh exits 0.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_FILE="${SCRIPT_DIR}/../observability_templates.yaml"
DRY_RUN="${1:-}"
FAILURES=0

GCP_PROJECT="amg-validation-2026-07-q3"
CLOUD_RUN_SERVICE="amg-campaign-agents"
REGION="us-central1"
BQ_DATASET="benchmark_metrics"
LOG_SINK_RUNS="amg-benchmark-runs-sink"
LOG_SINK_AUDIT="amg-audit-events-sink"

# ─── Helpers ──────────────────────────────────────────────────────────────────

log_info() { echo "[INFO]  $(date -u +%H:%M:%SZ)  $*"; }
log_ok()   { echo "[OK]    $(date -u +%H:%M:%SZ)  $*"; }
log_fail() { echo "[FAIL]  $(date -u +%H:%M:%SZ)  $*"; ((FAILURES++)) || true; }
log_skip() { echo "[SKIP]  $(date -u +%H:%M:%SZ)  $*"; }

run_or_skip() {
    local label="$1"; shift
    if [[ "$DRY_RUN" == "--dry-run" ]]; then
        log_skip "DRY-RUN: ${label}"
    else
        if "$@"; then
            log_ok "${label}"
        else
            log_fail "${label}"
        fi
    fi
}

# ─── Preamble ─────────────────────────────────────────────────────────────────

log_info "Deploying observability for campaign: ${GCP_PROJECT}"
log_info "Cloud Run service: ${CLOUD_RUN_SERVICE}"
log_info "Templates file: ${TEMPLATES_FILE}"
log_info "Dry-run: ${DRY_RUN:-false}"
echo ""

# ─── Cloud Logging: Create Run-Completion Sink ────────────────────────────────

log_info "Creating Cloud Logging sink: ${LOG_SINK_RUNS}..."
run_or_skip "create run-completion log sink" \
    gcloud logging sinks create "${LOG_SINK_RUNS}" \
        "bigquery.googleapis.com/projects/${GCP_PROJECT}/datasets/${BQ_DATASET}" \
        --project="${GCP_PROJECT}" \
        --log-filter='resource.type="cloud_run_revision" resource.labels.service_name="amg-campaign-agents" jsonPayload.event_type="run_complete"' \
        --description="Sink all run_complete events to BigQuery benchmark_metrics" \
        --quiet 2>/dev/null || \
    gcloud logging sinks update "${LOG_SINK_RUNS}" \
        "bigquery.googleapis.com/projects/${GCP_PROJECT}/datasets/${BQ_DATASET}" \
        --project="${GCP_PROJECT}" \
        --quiet

# ─── Cloud Logging: Create Audit Sink ─────────────────────────────────────────

log_info "Creating Cloud Logging sink: ${LOG_SINK_AUDIT}..."
run_or_skip "create T3 audit log sink" \
    gcloud logging sinks create "${LOG_SINK_AUDIT}" \
        "bigquery.googleapis.com/projects/${GCP_PROJECT}/datasets/${BQ_DATASET}" \
        --project="${GCP_PROJECT}" \
        --log-filter='resource.type="cloud_run_revision" resource.labels.service_name="amg-campaign-agents" jsonPayload.resource_type="memory_t3"' \
        --description="Sink T3 audit events to BigQuery" \
        --quiet 2>/dev/null || \
    gcloud logging sinks update "${LOG_SINK_AUDIT}" \
        "bigquery.googleapis.com/projects/${GCP_PROJECT}/datasets/${BQ_DATASET}" \
        --project="${GCP_PROJECT}" \
        --quiet

# ─── Cloud Trace: Enable 100% Sampling ────────────────────────────────────────

log_info "Enabling Cloud Trace 100% sampling on Cloud Run service..."
run_or_skip "set TRACE_SAMPLING_RATE=1.0 env var on Cloud Run" \
    gcloud run services update "${CLOUD_RUN_SERVICE}" \
        --region="${REGION}" \
        --project="${GCP_PROJECT}" \
        --update-env-vars="TRACE_SAMPLING_RATE=1.0,CAMPAIGN_ID=amg-campaign-2026-06-29" \
        --quiet

# ─── Cloud Monitoring: Cost Hard-Stop Alert ────────────────────────────────────

log_info "Creating alerting policy: cost hard-stop..."
# Alert policy JSON — matches observability_templates.yaml alerting_policies.amg-cost-hard-stop
HARD_STOP_POLICY_JSON='{
  "displayName": "AMG: Cost Hard-Stop Triggered",
  "conditions": [{
    "displayName": "Cost hard-stop log match",
    "conditionMatchedLog": {
      "filter": "jsonPayload.event_type=\"cost_hard_stop_triggered\""
    }
  }],
  "alertStrategy": {"autoClose": "604800s"},
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": []
}'
run_or_skip "create cost hard-stop alert policy" \
    bash -c "echo '${HARD_STOP_POLICY_JSON}' | \
        gcloud alpha monitoring policies create \
            --project=${GCP_PROJECT} \
            --policy-from-file=/dev/stdin --quiet"

# ─── Verify Deployment ────────────────────────────────────────────────────────

echo ""
log_info "Verifying deployment..."

if [[ "$DRY_RUN" != "--dry-run" ]]; then
    # Verify sinks exist
    if gcloud logging sinks describe "${LOG_SINK_RUNS}" --project="${GCP_PROJECT}" > /dev/null 2>&1; then
        log_ok "Log sink ${LOG_SINK_RUNS} active"
    else
        log_fail "Log sink ${LOG_SINK_RUNS} not found"
    fi

    if gcloud logging sinks describe "${LOG_SINK_AUDIT}" --project="${GCP_PROJECT}" > /dev/null 2>&1; then
        log_ok "Log sink ${LOG_SINK_AUDIT} active"
    else
        log_fail "Log sink ${LOG_SINK_AUDIT} not found"
    fi

    # Print dashboard URLs (manual creation via Console or terraform)
    SERVICE_URL="$(gcloud run services describe ${CLOUD_RUN_SERVICE} --region=${REGION} \
        --project=${GCP_PROJECT} --format='value(status.url)' 2>/dev/null || echo 'N/A')"
    echo ""
    log_info "Dashboard URLs (open in Cloud Console):"
    echo "  Logs Explorer:  https://console.cloud.google.com/logs/query;query=resource.type%3D%22cloud_run_revision%22%0Aresource.labels.service_name%3D%22${CLOUD_RUN_SERVICE}%22;project=${GCP_PROJECT}"
    echo "  Cloud Trace:    https://console.cloud.google.com/traces/list?project=${GCP_PROJECT}"
    echo "  Cloud Run URL:  ${SERVICE_URL}"
fi

# ─── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════════"
echo " Observability Deployment Summary"
echo " Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo " Failures:  ${FAILURES}"
echo "════════════════════════════════════════════════════"

if [[ ${FAILURES} -gt 0 ]]; then
    echo "❌ DECISION: HALT — ${FAILURES} deployment step(s) failed."
    exit 1
else
    echo "✅ DECISION: PROCEED to E7-exec-T3 (Launch Benchmarks)"
    exit 0
fi
