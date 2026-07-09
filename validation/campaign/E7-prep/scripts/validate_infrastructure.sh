#!/usr/bin/env bash
# E7-exec Infrastructure Validation Script
# Validates all GCP resources are healthy before launching benchmarks.
# Usage: ./scripts/validate_infrastructure.sh [--dry-run]
# Exit code: 0 = all checks passed, 1 = one or more checks failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_FILE="${SCRIPT_DIR}/../artifacts/E7-exec-infrastructure-validation-report.md"
DRY_RUN="${1:-}"
FAILURES=0
CHECKS_PASSED=0
CHECKS_TOTAL=0

GCP_PROJECT="amg-validation-2026-07-q3"
SPANNER_INSTANCE="amg-campaign-spanner"
SPANNER_DB="memory_db"
CLOUD_RUN_SERVICE="amg-campaign-agents"
REGION="us-central1"
GCS_CORPUS_BUCKET="amg-campaign-corpus-q3"
BQ_DATASETS=("raw_retail_public" "curated_retail_campaign" "benchmark_metrics")

# ─── Helpers ──────────────────────────────────────────────────────────────────

log_info()  { echo "[INFO]  $(date -u +%H:%M:%SZ)  $*"; }
log_pass()  { echo "[PASS]  $(date -u +%H:%M:%SZ)  $*"; ((CHECKS_PASSED++)) || true; ((CHECKS_TOTAL++)) || true; }
log_fail()  { echo "[FAIL]  $(date -u +%H:%M:%SZ)  $*"; ((FAILURES++)) || true; ((CHECKS_TOTAL++)) || true; }
log_skip()  { echo "[SKIP]  $(date -u +%H:%M:%SZ)  $*"; }

check() {
    local name="$1"
    local cmd="$2"
    if [[ "$DRY_RUN" == "--dry-run" ]]; then
        log_skip "DRY-RUN: $name"
        return 0
    fi
    if eval "$cmd" > /dev/null 2>&1; then
        log_pass "$name"
    else
        log_fail "$name — command: $cmd"
    fi
}

# ─── Preamble ─────────────────────────────────────────────────────────────────

log_info "Starting infrastructure validation for campaign: ${GCP_PROJECT}"
log_info "Spanner: ${SPANNER_INSTANCE}/${SPANNER_DB}"
log_info "Cloud Run: ${CLOUD_RUN_SERVICE} (${REGION})"
log_info "Dry-run: ${DRY_RUN:-false}"
echo ""

# ─── GCP Auth ─────────────────────────────────────────────────────────────────

log_info "Checking GCP authentication..."
check "gcloud auth active" "gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q '.'"
check "correct GCP project" "gcloud config get-value project | grep -q '${GCP_PROJECT}'"

# ─── Spanner ──────────────────────────────────────────────────────────────────

log_info "Checking Spanner..."
check "spanner instance exists" \
    "gcloud spanner instances describe ${SPANNER_INSTANCE} --project=${GCP_PROJECT}"
check "spanner instance state READY" \
    "gcloud spanner instances describe ${SPANNER_INSTANCE} --project=${GCP_PROJECT} --format='value(state)' | grep -q 'READY'"
check "spanner database exists" \
    "gcloud spanner databases describe ${SPANNER_DB} --instance=${SPANNER_INSTANCE} --project=${GCP_PROJECT}"
check "spanner memory_node table exists" \
    "gcloud spanner databases execute-sql ${SPANNER_DB} \
       --instance=${SPANNER_INSTANCE} --project=${GCP_PROJECT} \
       --sql='SELECT COUNT(*) FROM memory_node WHERE tenant_id=\"amg-campaign-svc\" LIMIT 1'"
check "spanner node count >= 100" \
    "gcloud spanner databases execute-sql ${SPANNER_DB} \
       --instance=${SPANNER_INSTANCE} --project=${GCP_PROJECT} \
       --sql='SELECT COUNT(*) AS cnt FROM memory_node' \
       --format='value(rows[0][0])' | awk '{if (\$1 >= 100) exit 0; else exit 1}'"

# ─── BigQuery ─────────────────────────────────────────────────────────────────

log_info "Checking BigQuery datasets..."
for dataset in "${BQ_DATASETS[@]}"; do
    check "bq dataset ${dataset} exists" \
        "bq ls --project_id=${GCP_PROJECT} | grep -q '${dataset}'"
done

check "bq raw_retail_public has data" \
    "bq query --nouse_legacy_sql --project_id=${GCP_PROJECT} \
       'SELECT COUNT(*) FROM \`${GCP_PROJECT}.raw_retail_public.INFORMATION_SCHEMA.TABLES\`' \
       | grep -qE '[1-9][0-9]*'"
check "bq benchmark_metrics.runs table exists" \
    "bq show --project_id=${GCP_PROJECT} benchmark_metrics.runs"
check "bq benchmark_metrics.cost_ledger table exists" \
    "bq show --project_id=${GCP_PROJECT} benchmark_metrics.cost_ledger"

# ─── GCS Corpus ───────────────────────────────────────────────────────────────

log_info "Checking GCS corpus..."
check "gcs corpus bucket accessible" \
    "gsutil ls gs://${GCS_CORPUS_BUCKET}/ > /dev/null"
check "gcs corpus has >= 1000 documents" \
    "gsutil ls gs://${GCS_CORPUS_BUCKET}/corpus/ | wc -l | awk '{if (\$1 >= 1000) exit 0; else exit 1}'"
check "gcs corpus manifest exists" \
    "gsutil stat gs://${GCS_CORPUS_BUCKET}/metadata/corpus_manifest.json"

# ─── Cloud Run ────────────────────────────────────────────────────────────────

log_info "Checking Cloud Run service..."
check "cloud run service exists" \
    "gcloud run services describe ${CLOUD_RUN_SERVICE} --region=${REGION} --project=${GCP_PROJECT}"
check "cloud run service ready" \
    "gcloud run services describe ${CLOUD_RUN_SERVICE} --region=${REGION} --project=${GCP_PROJECT} \
       --format='value(status.conditions[0].status)' | grep -q 'True'"

SERVICE_URL="$(gcloud run services describe ${CLOUD_RUN_SERVICE} --region=${REGION} \
    --project=${GCP_PROJECT} --format='value(status.url)' 2>/dev/null || echo '')"

if [[ -n "$SERVICE_URL" ]]; then
    check "cloud run health endpoint returns 200" \
        "curl -sf --max-time 15 ${SERVICE_URL}/health | grep -q '\"status\"'"
else
    log_fail "Could not retrieve Cloud Run service URL"
fi

# ─── Integrations ─────────────────────────────────────────────────────────────

log_info "Checking integrations (read-only health checks)..."
check "slack bot token secret exists" \
    "gcloud secrets describe amg-slack-bot-token --project=${GCP_PROJECT}"
check "jira api token secret exists" \
    "gcloud secrets describe amg-jira-api-token --project=${GCP_PROJECT}"
check "github pat secret exists" \
    "gcloud secrets describe amg-github-pat --project=${GCP_PROJECT}"
check "calendar service account key secret exists" \
    "gcloud secrets describe amg-calendar-sa-key --project=${GCP_PROJECT}"

# ─── Configuration Freeze ─────────────────────────────────────────────────────

log_info "Verifying configuration freeze (E6-T7)..."
check "freeze manifest exists in GCS" \
    "gsutil stat gs://${GCS_CORPUS_BUCKET}/config/freeze_manifest.yaml"

# ─── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════════"
echo " Infrastructure Validation Summary"
echo " Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo " Project:   ${GCP_PROJECT}"
echo "────────────────────────────────────────────────────"
echo " Checks Passed: ${CHECKS_PASSED}"
echo " Checks Failed: ${FAILURES}"
echo " Total Checks:  ${CHECKS_TOTAL}"
echo "════════════════════════════════════════════════════"

# Write report file
mkdir -p "$(dirname "$REPORT_FILE")"
cat > "$REPORT_FILE" << REPORT_EOF
# E7-exec Infrastructure Validation Report

**Timestamp:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Project:** ${GCP_PROJECT}
**Checks Passed:** ${CHECKS_PASSED}
**Checks Failed:** ${FAILURES}
**Total Checks:** ${CHECKS_TOTAL}
**Decision:** $([ ${FAILURES} -eq 0 ] && echo "✅ PROCEED to E7-exec-T2 (Deploy Observability)" || echo "❌ HALT — fix ${FAILURES} failing checks before proceeding")

REPORT_EOF

if [[ ${FAILURES} -gt 0 ]]; then
    echo ""
    echo "❌ DECISION: HALT — ${FAILURES} check(s) failed. Fix before proceeding."
    echo "   See report: ${REPORT_FILE}"
    exit 1
else
    echo ""
    echo "✅ DECISION: PROCEED to E7-exec-T2 (Deploy Observability)"
    echo "   See report: ${REPORT_FILE}"
    exit 0
fi
