# E5-T7 — Runtime Prerequisites and Service Provisioning

**Epic:** E5 — Deferred GCP Bootstrap and Runtime Provisioning
**Task:** E5-T7
**Date:** 2026-07-09
**Status:** Approved
**Owner:** Infrastructure Lead

---

## 1. Objective

Provision all runtime infrastructure for the campaign: BigQuery datasets, Spanner graph database, Cloud Run agent service, and verify all systems are operational and healthy.

**Dependencies:** E5-T1 (variables), E5-T2 (Terraform), E5-T3 (APIs), E5-T4 (budget), E5-T5 (IAM), E5-T6 (labels)

**Blocking:** E6 (data provisioning) and E7 (measured execution) both depend on E5-T7 completion.

---

## 2. BigQuery Datasets and Schema

### 2.1 Create Datasets

**Three datasets (from E3-T1 frozen schema):**

| Dataset | Purpose | Tables | Owner | Location |
|---------|---------|--------|-------|----------|
| `raw_retail_public` | Raw data from sources (DS-01–DS-06) | ~10 tables (customers, products, orders, etc.) | Data Lead | US multi-region |
| `curated_retail_campaign` | Transformed business entities | ~10 tables (same schema, cleansed) | Data Lead | US multi-region |
| `benchmark_metrics` | KPI results and cost ledger | 5+ tables (runs, cost_ledger, analytics, agent_analytics, etc.) | Infrastructure Lead | US multi-region |

### 2.2 Create Datasets via Terraform

```hcl
# terraform/bigquery.tf
resource "google_bigquery_dataset" "raw_retail_public" {
  dataset_id    = "raw_retail_public"
  friendly_name = "Raw Retail Data (Public/Synthetic)"
  description   = "Raw data from sources DS-01 through DS-06"
  project       = var.project_id
  location      = "US"

  access {
    role          = "OWNER"
    user_by_email = google_service_account.campaign_svc.email
  }

  labels = local.campaign_labels
}

resource "google_bigquery_dataset" "curated_retail_campaign" {
  dataset_id    = "curated_retail_campaign"
  friendly_name = "Curated Retail Data"
  description   = "Business-ready transformed entities"
  project       = var.project_id
  location      = "US"

  access {
    role          = "OWNER"
    user_by_email = google_service_account.campaign_svc.email
  }

  labels = local.campaign_labels
}

resource "google_bigquery_dataset" "benchmark_metrics" {
  dataset_id    = "benchmark_metrics"
  friendly_name = "Campaign Benchmark Metrics"
  description   = "KPI results, cost tracking, analytics"
  project       = var.project_id
  location      = "US"

  access {
    role          = "OWNER"
    user_by_email = google_service_account.campaign_svc.email
  }

  labels = local.campaign_labels
}
```

### 2.3 Create Tables (from E4-T3 frozen schema)

**benchmark_metrics.runs** (primary table from E4-T3):

```sql
CREATE TABLE `{{PROJECT_ID}}.benchmark_metrics.runs` (
  run_id STRING NOT NULL,
  campaign_id STRING NOT NULL,
  scenario_id STRING NOT NULL,
  agent_id STRING NOT NULL,
  execution_timestamp_utc TIMESTAMP NOT NULL,
  week INT64,
  warmup_flag BOOL,
  seed_run_index INT64,
  model_name STRING,
  model_version STRING,
  prompt_template_id STRING,
  input_tokens INT64,
  output_tokens INT64,
  total_tokens INT64,
  estimated_cost_usd NUMERIC(7, 4),
  response_text STRING,
  task_success BOOL,
  groundedness_score NUMERIC(3, 2),
  error_occurred BOOL,
  error_type STRING,
  retrieved_docs ARRAY<STRUCT<source STRING, source_id STRING, rank INT64, relevance_score FLOAT64>>,
  retrieved_doc_count INT64,
  graph_traversal_hops INT64,
  total_bq_rows_scanned INT64,
  observability_trace_id STRING,
  audit_log_entry_ids ARRAY<STRING>
)
PARTITION BY execution_timestamp_utc
CLUSTER BY campaign_id, scenario_id, agent_id
WITH CONNECTION OPTIONS (
  dataset_id = "benchmark_metrics",
  labels = {"campaign": "validation-2026", "owner": "product-team", "env": "campaign"}
);
```

**benchmark_metrics.cost_ledger** (from E4-T6):

```sql
CREATE TABLE `{{PROJECT_ID}}.benchmark_metrics.cost_ledger` (
  ledger_id STRING NOT NULL,
  campaign_id STRING NOT NULL,
  transaction_date DATE NOT NULL,
  cost_category STRING,  -- BigQuery, Spanner, Vertex AI, Cloud Run, etc.
  amount_usd NUMERIC(10, 4),
  run_id STRING,
  agent_id STRING,
  scenario_id STRING,
  gcp_billing_project_id STRING,
  status STRING,  -- estimated, reconciled, hard_stop, final
  created_timestamp TIMESTAMP NOT NULL
)
PARTITION BY transaction_date
CLUSTER BY campaign_id, cost_category
WITH CONNECTION OPTIONS (
  labels = {"campaign": "validation-2026", "owner": "product-team", "env": "campaign"}
);
```

---

## 3. Spanner Graph Database

### 3.1 Create Spanner Instance

```bash
gcloud spanner instances create {{SPANNER_INSTANCE_ID}} \
  --config=multi-region-us \
  --display-name="Campaign Memory Storage" \
  --nodes=1 \
  --labels=campaign=validation-2026,owner=product-team,env=campaign,ttl=6-weeks,auto_delete=true \
  --project={{PROJECT_ID}}
```

### 3.2 Create Spanner Database

```bash
gcloud spanner databases create {{SPANNER_DB_NAME}} \
  --instance={{SPANNER_INSTANCE_ID}} \
  --project={{PROJECT_ID}}
```

### 3.3 Apply Schema Migrations

**Migrations from `/migrations/001_*.sql` through `011_*.sql` (frozen in E3):**

```bash
# Apply all migrations sequentially
for migration in /migrations/00{1..9}_*.sql /migrations/01{0..1}_*.sql; do
  echo "Applying migration: $migration"
  gcloud spanner databases ddl update {{SPANNER_DB_NAME}} \
    --instance={{SPANNER_INSTANCE_ID}} \
    --ddl-file="$migration" \
    --project={{PROJECT_ID}}
done

# Verify schema
gcloud spanner databases describe {{SPANNER_DB_NAME}} \
  --instance={{SPANNER_INSTANCE_ID}} \
  --project={{PROJECT_ID}}
```

### 3.4 Spanner Terraform

```hcl
# terraform/spanner.tf
resource "google_spanner_instance" "campaign" {
  name             = "{{SPANNER_INSTANCE_ID}}"
  config           = "multi-region-us"
  display_name     = "Campaign Memory Storage"
  num_nodes        = 1
  project          = var.project_id
  labels           = local.campaign_labels
}

resource "google_spanner_database" "memory_db" {
  instance  = google_spanner_instance.campaign.name
  name      = "{{SPANNER_DB_NAME}}"
  project   = var.project_id

  ddl = [
    # DDL from migrations 001–011
    file("${path.module}/../migrations/001_memory_node_table.sql"),
    file("${path.module}/../migrations/002_memory_edge_table.sql"),
    # ... etc
  ]
}
```

### 3.5 Verify Spanner Health

```bash
# Check instance status
gcloud spanner instances describe {{SPANNER_INSTANCE_ID}} \
  --project={{PROJECT_ID}}

# Query database schema
gcloud spanner databases ddl describe {{SPANNER_DB_NAME}} \
  --instance={{SPANNER_INSTANCE_ID}} \
  --project={{PROJECT_ID}}

# Test connectivity (insert 1 row, verify 1 result)
gcloud spanner rows insert --table=memory_nodes --instance={{SPANNER_INSTANCE_ID}} \
  --database={{SPANNER_DB_NAME}} \
  --project={{PROJECT_ID}} \
  --data='node_id=test-node-001,label=Customer,payload={}'
```

---

## 4. Cloud Run Agent Service

### 4.1 Build and Push Container Image

**Source:** Agent backend code (Python FastAPI)

```bash
# Build Docker image
docker build -t {{REGION}}-docker.pkg.dev/{{PROJECT_ID}}/amg-campaign/agents:latest \
  -f Dockerfile .

# Authenticate with Artifact Registry
gcloud auth configure-docker {{REGION}}-docker.pkg.dev

# Push to Artifact Registry
docker push {{REGION}}-docker.pkg.dev/{{PROJECT_ID}}/amg-campaign/agents:latest
```

### 4.2 Deploy Cloud Run Service

```bash
gcloud run deploy {{CLOUD_RUN_SERVICE}} \
  --image={{REGION}}-docker.pkg.dev/{{PROJECT_ID}}/amg-campaign/agents:latest \
  --region={{REGION}} \
  --platform=managed \
  --service-account=amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com \
  --memory=2Gi \
  --cpu=2 \
  --timeout=3600 \
  --max-instances=100 \
  --min-instances=1 \
  --labels=campaign=validation-2026,owner=product-team,env=campaign \
  --set-env-vars="PROJECT_ID={{PROJECT_ID}},SPANNER_INSTANCE={{SPANNER_INSTANCE_ID}},SPANNER_DB={{SPANNER_DB_NAME}}" \
  --allow-unauthenticated=false \
  --project={{PROJECT_ID}}
```

### 4.3 Cloud Run Terraform

```hcl
# terraform/cloudrun.tf
resource "google_cloud_run_service" "agents" {
  name     = "{{CLOUD_RUN_SERVICE}}"
  location = var.region
  project  = var.project_id

  template {
    spec {
      service_account_name = google_service_account.campaign_svc.email
      timeout_seconds      = 3600

      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/amg-campaign/agents:latest"

        resources {
          limits = {
            memory = "2Gi"
            cpu    = "2"
          }
        }

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "SPANNER_INSTANCE"
          value = google_spanner_instance.campaign.name
        }
        env {
          name  = "SPANNER_DB"
          value = google_spanner_database.memory_db.name
        }
      }
    }

    metadata {
      labels = local.campaign_labels
    }
  }

  labels = local.campaign_labels

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Block unauthenticated access
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  service = google_cloud_run_service.agents.name
  location = var.region
  role    = "roles/run.invoker"
  member  = "serviceAccount:amg-campaign-scheduler@${var.project_id}.iam.gserviceaccount.com"
  project = var.project_id
}
```

### 4.4 Health Check and Smoke Test

```bash
# Get Cloud Run service URL
SERVICE_URL=$(gcloud run services describe {{CLOUD_RUN_SERVICE}} \
  --region={{REGION}} \
  --project={{PROJECT_ID}} \
  --format='value(status.url)')

echo "Cloud Run service URL: $SERVICE_URL"

# Call health endpoint (assuming /health path exists)
curl -s "$SERVICE_URL/health" \
  --header "Authorization: Bearer $(gcloud auth print-access-token)" | jq .

# Expected response: {"status": "healthy", "version": "..."}
```

---

## 5. Observability Integration

### 5.1 Cloud Logging Configuration

```bash
# Create log sink for T3 audit events (Spanner writes)
gcloud logging sinks create amg-campaign-audit-sink \
  logging.googleapis.com/projects/{{PROJECT_ID}}/logs/spanner_audit \
  --project={{PROJECT_ID}} \
  --log-filter='resource.type="cloud_spanner" AND jsonPayload.event_type=~"(audit|write)"'
```

### 5.2 Cloud Trace Configuration

```bash
# Verify Cloud Trace API is enabled
gcloud services describe cloudtrace.googleapis.com \
  --project={{PROJECT_ID}}

# Note: Agent code must explicitly create spans via Trace client
# (See agent implementation for span creation)
```

### 5.3 Cloud Monitoring Dashboards

Already created in E5-T4 (budget + cost). Observability dashboard created in E4-T4 design.

---

## 6. Runtime Verification Checklist

### 6.1 BigQuery Datasets

| Dataset | Status | Tables | Owner | Verified |
|---------|--------|--------|-------|----------|
| raw_retail_public | ☐ Created | ☐ Empty (ready for E6 data load) | Data Lead | ☐ |
| curated_retail_campaign | ☐ Created | ☐ Empty | Data Lead | ☐ |
| benchmark_metrics | ☐ Created | ☐ Empty | Infrastructure Lead | ☐ |

**Verification commands:**
```bash
bq ls --project={{PROJECT_ID}} --dataset_id=raw_retail_public
bq ls --project={{PROJECT_ID}} --dataset_id=curated_retail_campaign
bq ls --project={{PROJECT_ID}} --dataset_id=benchmark_metrics
```

### 6.2 Spanner Instance and Database

| Item | Status | Owner | Verified |
|------|--------|-------|----------|
| Instance created (amg-campaign-spanner) | ☐ | Infrastructure Lead | ☐ |
| Database created (memory_db) | ☐ | Infrastructure Lead | ☐ |
| Schema applied (11 migrations) | ☐ | Data Lead | ☐ |
| Test row inserted and queried | ☐ | Infrastructure Lead | ☐ |
| Replication healthy | ☐ | Infrastructure Lead | ☐ |

**Verification queries:**
```bash
# Test read
gcloud spanner databases query-plan {{SPANNER_DB_NAME}} \
  --instance={{SPANNER_INSTANCE_ID}} \
  --project={{PROJECT_ID}} \
  --sql="SELECT COUNT(*) FROM memory_nodes"

# Test write (idempotent)
gcloud spanner databases execute-sql {{SPANNER_DB_NAME}} \
  --instance={{SPANNER_INSTANCE_ID}} \
  --project={{PROJECT_ID}} \
  --sql="MERGE INTO memory_nodes KEY(node_id) VALUES('verify-001', 'VerifyNode', '{}')"
```

### 6.3 Cloud Run Service

| Item | Status | Owner | Verified |
|------|--------|-------|----------|
| Image built and pushed to Artifact Registry | ☐ | Backend Engineer | ☐ |
| Cloud Run service deployed | ☐ | Infrastructure Lead | ☐ |
| Service account linked | ☐ | Infrastructure Lead | ☐ |
| Health endpoint returns 200 OK | ☐ | Backend Engineer | ☐ |
| Can access Spanner (test query) | ☐ | Backend Engineer | ☐ |
| Can access BigQuery (test query) | ☐ | Backend Engineer | ☐ |
| Can retrieve secrets from Secret Manager | ☐ | Backend Engineer | ☐ |

**Verification commands:**
```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe {{CLOUD_RUN_SERVICE}} \
  --region={{REGION}} --project={{PROJECT_ID}} --format='value(status.url)')

# Health check
curl "$SERVICE_URL/health" \
  --header "Authorization: Bearer $(gcloud auth print-access-token)"

# Expected: {"status": "healthy", "version": "..."}
```

### 6.4 Observability

| Item | Status | Owner | Verified |
|------|--------|-------|----------|
| Cloud Logging sink created | ☐ | Infrastructure Lead | ☐ |
| Cloud Trace API enabled | ☐ | Infrastructure Lead | ☐ |
| Cloud Monitoring dashboard accessible | ☐ | Infrastructure Lead | ☐ |
| Test trace created and visible | ☐ | Backend Engineer | ☐ |

---

## 7. Resource Summary

**After E5-T7 completion, the following resources will be live:**

| Resource Type | Name | Region | Owner | Cost/Mo |
|---------------|------|--------|-------|---------|
| Spanner Instance | amg-campaign-spanner | Multi-region US | Infrastructure | $1.20 |
| Spanner Database | memory_db | Multi-region US | Infrastructure | (included) |
| BigQuery Datasets | 3 datasets | US | Data Lead | $0.00 (pay per query) |
| Cloud Run Service | amg-campaign-agents | us-central1 | Infrastructure | $0.20–$2.00 |
| GCS Buckets | 3 buckets | us-central1 | Infrastructure | $0.05–$0.20 |
| Cloud Monitoring Dashboard | 2–3 dashboards | Global | Infrastructure | $0.00 |

**Total estimated monthly cost (Week 4 only):** ~USD 40–50 (infrastructure) + measured execution (E6/E7)

---

## 8. Sign-Off Checklist

| Item | Owner | Sign-Off | Date |
|------|-------|----------|------|
| All 3 BigQuery datasets created | Data Lead | ☐ | ____ |
| Spanner instance and database healthy | Infrastructure Lead | ☐ | ____ |
| Cloud Run service deployed and responsive | Backend Engineer | ☐ | ____ |
| Smoke tests passed (all services accessible) | Infrastructure Lead | ☐ | ____ |
| Labels applied to all resources | Infrastructure Lead | ☐ | ____ |
| Observability pipeline functional | Infrastructure Lead | ☐ | ____ |
| Cost monitoring active (budget alerts working) | Finance Lead | ☐ | ____ |
| Ready for E5-T8 gate review | Program Manager | ☐ | ____ |
