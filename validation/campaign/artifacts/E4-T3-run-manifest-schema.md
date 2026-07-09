# E4-T3 — Run Manifest Schema

**Epic:** E4 — Benchmark, Observability, and Cost Control Design
**Task:** E4-T3
**Date:** 2026-07-08
**Status:** Approved
**Owner:** MLE Lead

---

## 1. Run Manifest Purpose

The **run manifest** is the canonical schema for capturing metadata from a single benchmark execution. It:
- Maps to the BigQuery `benchmark_metrics` table (defined in E3-T1)
- Records all inputs, outputs, and cost/timing observations
- Enables traceability from a campaign result back to exact model version, prompt, config, and seed data
- Supports cost ledger tracking (E4-T6) and KPI calculations (E4-T5)

---

## 2. Run Manifest Schema (JSON/Record Format)

### 2.1 Identity Fields

```json
{
  "run_id": "string (UUID v4)",
  "campaign_id": "string (amg-campaign-2026-06-29)",
  "scenario_id": "string (EMC-001...EMC-012)",
  "agent_id": "string (AGENT-EC, AGENT-CC, AGENT-TA, AGENT-SI, AGENT-CM, AGENT-CA)",
  "scenario_version": "string (v1.0)"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | UUID | ✓ | Globally unique; generated at E6-T1 runtime |
| `campaign_id` | string | ✓ | Fixed: `amg-campaign-2026-06-29` |
| `scenario_id` | string | ✓ | Valid enum: EMC-001 through EMC-012 |
| `agent_id` | string | ✓ | Valid enum: from E2-T2 agent profiles |
| `scenario_version` | string | ✓ | Frozen after E4 gate; currently `v1.0` |

---

### 2.2 Execution Context

```json
{
  "execution_timestamp_utc": "RFC3339 timestamp",
  "execution_week": "integer (4 or 5 or 6)",
  "warmup_flag": "boolean",
  "seed_run_index": "integer (0-29)"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `execution_timestamp_utc` | RFC3339 | ✓ | ISO 8601; e.g., "2026-07-15T14:30:00Z" |
| `execution_week` | int | ✓ | Week of campaign (4=Week 4, etc.) |
| `warmup_flag` | boolean | ✓ | true if this is a dry-run or cache warm-up; false for measured run |
| `seed_run_index` | int | ✓ | 0–29 (each scenario runs 30 times); orders runs for reproducibility |

---

### 2.3 Configuration and Version Pinning

```json
{
  "model_name": "string (gemini-1.5-flash or gemini-1.5-pro)",
  "model_version": "string (snapshot identifier)",
  "prompt_template_id": "string",
  "prompt_version": "string (v1.0, v1.1, etc.)",
  "config_hash": "string (SHA256 of frozen config JSON)"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `model_name` | string | ✓ | Per agent profile (E2-T2): EC/CC→Flash; TA/CA→Pro; SI→Flash; CM→Flash |
| `model_version` | string | ✓ | Gemini version tag; enables roll-back tracking |
| `prompt_template_id` | string | ✓ | Unique ID for each agent's system prompt (e.g., `prompt-ec-001`) |
| `prompt_version` | string | ✓ | Version of prompt; incremented if prompt changes mid-campaign |
| `config_hash` | string | ✓ | SHA256(frozen_runtime_config JSON); detects undocumented config drift |

**Config JSON to hash:** temperature, max_tokens, top_p, top_k, memory_tiers (T1/T2/T3 access), retrieval_method (e.g., "graph_then_corpus"), score_thresholds

---

### 2.4 Input Data and Seed

```json
{
  "seed_dataset_ids": ["raw_retail_public:DS-01", "raw_retail_public:DS-02", ...],
  "seed_corpus_types": ["CORP-01", "CORP-02", "CORP-03", ...],
  "no_evidence_fixture_ids": ["NE-001", "NE-002", ...],
  "seed_graph_node_count": "integer",
  "seed_graph_edge_count": "integer"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `seed_dataset_ids` | string[] | ✓ | Data sources loaded at E5-T4; e.g., `["DS-01", "DS-02", "DS-03"]` |
| `seed_corpus_types` | string[] | ✓ | Corpus types seeded; e.g., `["CORP-01", "CORP-02", "CORP-03"]` |
| `no_evidence_fixture_ids` | string[] | ✓ | Fixed UUIDs inserted to test no-evidence paths; e.g., `["NE-001", "NE-002", "NE-003", "NE-004", "NE-005"]` |
| `seed_graph_node_count` | int | ✓ | Total nodes in Spanner at start of run |
| `seed_graph_edge_count` | int | ✓ | Total edges in Spanner at start of run |

---

### 2.5 Latency and Performance

```json
{
  "latency_total_ms": "integer (milliseconds)",
  "latency_breakdown": {
    "retrieval_ms": "integer",
    "inference_ms": "integer",
    "external_api_ms": "integer"
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `latency_total_ms` | int | ✓ | End-to-end wall-clock time from user query to response delivery |
| `latency_breakdown.retrieval_ms` | int | ✓ | Time spent querying Spanner + BigQuery + corpus storage |
| `latency_breakdown.inference_ms` | int | ✓ | Time spent in LLM API call (excluding I/O) |
| `latency_breakdown.external_api_ms` | int | ✓ | Time in external APIs (Slack, Calendar, GitHub, etc.); 0 if not applicable |

---

### 2.6 Token and Cost Tracking

```json
{
  "input_tokens": "integer",
  "output_tokens": "integer",
  "total_tokens": "integer",
  "estimated_cost_usd": "numeric (2 decimals)"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `input_tokens` | int | ✓ | Tokens passed to LLM (prompt + retrieved context) |
| `output_tokens` | int | ✓ | Tokens generated by LLM in response |
| `total_tokens` | int | ✓ | input_tokens + output_tokens |
| `estimated_cost_usd` | numeric | ✓ | Cost = (input_tokens × input_rate + output_tokens × output_rate) for selected model |

**Pricing assumptions (E4-T6 cost ledger)::**
- Gemini 1.5 Flash: $0.075/1M input, $0.30/1M output
- Gemini 1.5 Pro: $1.50/1M input, $6.00/1M output

---

### 2.7 Response and Scoring

```json
{
  "response_text": "string (full agent response)",
  "response_length_chars": "integer",
  "task_success": "boolean (0 or 1)",
  "groundedness_score": "numeric (0.0–1.0)",
  "scorer_id": "string (user email or 'auto')",
  "scoring_timestamp_utc": "RFC3339",
  "final_regrade": "boolean (default: false)"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `response_text` | string | ✓ | Complete output from agent; used for groundedness review |
| `response_length_chars` | int | ✓ | Character count; enables brevity vs. verbosity analysis |
| `task_success` | boolean | ✓ | 0 or 1; per E4-T2 rubric |
| `groundedness_score` | numeric | ✓ | 0.0–1.0; per E4-T2 rubric |
| `scorer_id` | string | ✓ | If auto-graded, "auto"; if manual, user email of MLE who scored |
| `scoring_timestamp_utc` | RFC3339 | ✓ | When score was recorded; enables audit trail |
| `final_regrade` | boolean | ✗ | true if this run was re-graded after initial appeal; false or absent otherwise |

---

### 2.8 Retrieval Evidence (for groundedness audit)

```json
{
  "retrieved_docs": [
    {
      "source": "string (corpus | graph | bq)",
      "source_id": "string (doc_id | node_id | table_name)",
      "rank": "integer (1, 2, 3, ...)",
      "relevance_score": "numeric (0.0–1.0)"
    }
  ],
  "graph_traversal_hops": "integer",
  "total_bq_rows_scanned": "integer"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `retrieved_docs[].source` | enum | ✓ | "corpus" = GCS text doc; "graph" = Spanner node; "bq" = BigQuery row |
| `retrieved_docs[].source_id` | string | ✓ | Reference for audit traceability |
| `retrieved_docs[].rank` | int | ✓ | Retrieval rank (1st, 2nd, 3rd, ...); enables relevance analysis |
| `retrieved_docs[].relevance_score` | numeric | ✓ | Embedding similarity or BM25 score (0.0–1.0 normalized) |
| `graph_traversal_hops` | int | ✓ | Number of graph hops needed to answer query; proxy for reasoning complexity |
| `total_bq_rows_scanned` | int | ✓ | BigQuery rows examined (not necessarily returned); cost proxy |

---

### 2.9 Errors and Anomalies

```json
{
  "error_occurred": "boolean",
  "error_type": "string (optional; e.g., 'timeout', 'api_error', 'no_evidence')",
  "error_message": "string (optional; full exception text)",
  "fallback_used": "boolean (default: false)",
  "fallback_strategy": "string (optional; e.g., 'direct_bq', 'hardcoded_response')"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `error_occurred` | boolean | ✓ | true if exception was raised; false otherwise |
| `error_type` | string | ✗ | Standard categories: timeout, api_error, no_evidence, auth_error, malformed_input |
| `error_message` | string | ✗ | Full stack trace or API error message; omitted if no error |
| `fallback_used` | boolean | ✓ | true if agent triggered fallback behavior (e.g., direct BQ query after graph timeout) |
| `fallback_strategy` | string | ✗ | Name of fallback route; enables fallback effectiveness analysis |

---

### 2.10 Audit and Trace References

```json
{
  "audit_log_entry_ids": ["uuid", "uuid", ...],
  "observability_trace_id": "string (from E4-T4 tracing schema)",
  "campaign_tags": {
    "campaign": "validation-2026",
    "owner": "product-team",
    "env": "campaign",
    "ttl": "6-weeks",
    "auto_delete": "true"
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `audit_log_entry_ids` | string[] | ✓ | T3 audit event UUIDs for this run; enables end-to-end traceability |
| `observability_trace_id` | string | ✓ | Trace ID from E4-T4; enables correlation with Cloud Trace |
| `campaign_tags` | object | ✓ | Frozen label set from E1-T5; used for resource cleanup (auto_delete after TTL) |

---

## 3. BigQuery `benchmark_metrics` Table DDL

```sql
CREATE OR REPLACE TABLE `{{PROJECT_ID}}.benchmark_metrics.runs` (
  -- Identity
  run_id STRING NOT NULL,
  campaign_id STRING NOT NULL,
  scenario_id STRING NOT NULL,
  agent_id STRING NOT NULL,
  scenario_version STRING NOT NULL,

  -- Execution
  execution_timestamp_utc TIMESTAMP NOT NULL,
  execution_week INT64 NOT NULL,
  warmup_flag BOOL NOT NULL,
  seed_run_index INT64 NOT NULL,

  -- Configuration
  model_name STRING NOT NULL,
  model_version STRING NOT NULL,
  prompt_template_id STRING NOT NULL,
  prompt_version STRING NOT NULL,
  config_hash STRING NOT NULL,

  -- Input Data
  seed_dataset_ids ARRAY<STRING> NOT NULL,
  seed_corpus_types ARRAY<STRING> NOT NULL,
  no_evidence_fixture_ids ARRAY<STRING> NOT NULL,
  seed_graph_node_count INT64 NOT NULL,
  seed_graph_edge_count INT64 NOT NULL,

  -- Latency
  latency_total_ms INT64 NOT NULL,
  latency_retrieval_ms INT64 NOT NULL,
  latency_inference_ms INT64 NOT NULL,
  latency_external_api_ms INT64 NOT NULL,

  -- Cost
  input_tokens INT64 NOT NULL,
  output_tokens INT64 NOT NULL,
  total_tokens INT64 NOT NULL,
  estimated_cost_usd NUMERIC(7, 4) NOT NULL,

  -- Response & Scoring
  response_text STRING NOT NULL,
  response_length_chars INT64 NOT NULL,
  task_success BOOL NOT NULL,
  groundedness_score NUMERIC(3, 2) NOT NULL,
  scorer_id STRING NOT NULL,
  scoring_timestamp_utc TIMESTAMP NOT NULL,
  final_regrade BOOL,

  -- Retrieval Evidence
  retrieved_docs ARRAY<STRUCT<
    source STRING,
    source_id STRING,
    rank INT64,
    relevance_score NUMERIC(3, 2)
  >> NOT NULL,
  graph_traversal_hops INT64 NOT NULL,
  total_bq_rows_scanned INT64 NOT NULL,

  -- Errors
  error_occurred BOOL NOT NULL,
  error_type STRING,
  error_message STRING,
  fallback_used BOOL NOT NULL,
  fallback_strategy STRING,

  -- Audit
  audit_log_entry_ids ARRAY<STRING> NOT NULL,
  observability_trace_id STRING NOT NULL,
  campaign_tags STRUCT<
    campaign STRING,
    owner STRING,
    env STRING,
    ttl STRING,
    auto_delete STRING
  > NOT NULL,

  -- Metadata
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),

  PRIMARY KEY (run_id),
  CONSTRAINT task_success_valid CHECK (task_success IN (TRUE, FALSE)),
  CONSTRAINT groundedness_valid CHECK (groundedness_score >= 0.0 AND groundedness_score <= 1.0)
) PARTITION BY DATE(execution_timestamp_utc)
CLUSTER BY campaign_id, scenario_id, agent_id;
```

---

## 4. Run Manifest JSON Example

```json
{
  "run_id": "run-2026-07-15-001",
  "campaign_id": "amg-campaign-2026-06-29",
  "scenario_id": "EMC-002",
  "agent_id": "AGENT-EC",
  "scenario_version": "v1.0",
  "execution_timestamp_utc": "2026-07-15T14:30:15Z",
  "execution_week": 4,
  "warmup_flag": false,
  "seed_run_index": 5,
  "model_name": "gemini-1.5-flash",
  "model_version": "001",
  "prompt_template_id": "prompt-ec-001",
  "prompt_version": "v1.0",
  "config_hash": "abc123def456...",
  "seed_dataset_ids": ["DS-01", "DS-02", "DS-03"],
  "seed_corpus_types": ["CORP-01", "CORP-02"],
  "no_evidence_fixture_ids": ["NE-001", "NE-002"],
  "seed_graph_node_count": 50000,
  "seed_graph_edge_count": 120000,
  "latency_total_ms": 7500,
  "latency_breakdown": {
    "retrieval_ms": 3200,
    "inference_ms": 3800,
    "external_api_ms": 500
  },
  "input_tokens": 1250,
  "output_tokens": 340,
  "total_tokens": 1590,
  "estimated_cost_usd": 0.0119,
  "response_text": "Urgent tickets have an SLA of 4 hours for initial response, as documented in our escalation procedures SOP (sop_doc_id_42).",
  "response_length_chars": 127,
  "task_success": true,
  "groundedness_score": 1.0,
  "scorer_id": "auto",
  "scoring_timestamp_utc": "2026-07-15T14:30:45Z",
  "final_regrade": false,
  "retrieved_docs": [
    {
      "source": "corpus",
      "source_id": "sop_doc_id_42",
      "rank": 1,
      "relevance_score": 0.92
    }
  ],
  "graph_traversal_hops": 0,
  "total_bq_rows_scanned": 1,
  "error_occurred": false,
  "fallback_used": false,
  "audit_log_entry_ids": ["audit-uuid-001", "audit-uuid-002"],
  "observability_trace_id": "trace-2026-07-15-001",
  "campaign_tags": {
    "campaign": "validation-2026",
    "owner": "product-team",
    "env": "campaign",
    "ttl": "6-weeks",
    "auto_delete": "true"
  }
}
```

---

## 5. Validation Rules and Constraints

| Rule | Enforcement | Error Action |
|------|-----------|--------------|
| run_id must be unique | PRIMARY KEY in BigQuery + application-level UUIDv4 generation | Reject duplicate at E6-T1 |
| scenario_id must be valid enum (EMC-001–EMC-012) | Schema validation | Reject invalid run |
| task_success must be 0 or 1 | BQ CHECK constraint | Reject non-boolean value |
| groundedness_score must be ∈ [0.0, 1.0] | BQ CHECK constraint | Reject out-of-range value |
| All latency fields must be non-negative integers | Schema validation + BQ CHECK | Reject negative values |
| estimated_cost_usd must match token-based calculation | Formula: (input_tokens × rate_in + output_tokens × rate_out) | Post-load validation warning if drift > 1% |
| retrieved_docs.relevance_score must be ∈ [0.0, 1.0] | Schema validation | Reject invalid score |

---

## 6. Manifest Validation Checklist (E4-T7 Dry-Run)

| Item | Status | Notes |
|------|--------|-------|
| ☐ All required fields present in example | | task_success, groundedness_score cannot be NULL |
| ☐ All fields match BigQuery schema | | Run test insert; verify no type errors |
| ☐ Latency breakdown sums to ≤ latency_total_ms | | Validate: retrieval + inference + external_api ≤ total |
| ☐ Cost calculation verified | | Test: (tokens × rates) ≈ estimated_cost_usd ±1% |
| ☐ UUID run_id is unique across all test runs | | Run 10 test inserts; verify no collisions |
| ☐ Config hash is reproducible | | Same config JSON → same SHA256 hash |
| ☐ Audit log entry IDs reference actual T3 records | | Spot-check: select from audit table; verify entries exist |
