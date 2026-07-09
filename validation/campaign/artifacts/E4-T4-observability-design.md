# E4-T4 — Observability Event Schema and Tracing Design

**Epic:** E4 — Benchmark, Observability, and Cost Control Design
**Task:** E4-T4
**Date:** 2026-07-08
**Status:** Approved
**Owner:** Infrastructure Lead

---

## 1. Observability Architecture

The observability stack captures:
1. **T3 Audit Events** (immutable; every external action logged)
2. **Cloud Trace** (distributed tracing; latency and dependency chains)
3. **BigQuery Agent Analytics** (aggregated execution events)

**Guarantee:** Every run produces at least one T3 audit event, one Cloud Trace record, and one BigQuery analytics row.

---

## 2. T3 Audit Event Schema

**Purpose:** Immutable record of every external API call, memory access, and decision point.

### 2.1 Audit Event Structure

```json
{
  "event_id": "UUID (v4)",
  "event_timestamp_utc": "RFC3339",
  "campaign_id": "string",
  "run_id": "string",
  "event_type": "enum (see §2.2)",
  "agent_id": "string",
  "tenant_id": "string (amg-campaign-svc for campaign)",
  "severity": "enum (INFO, WARN, ERROR, CRITICAL)",
  "action": "string (what was attempted: read_t1, write_t2, api_call_external, graph_query)",
  "resource_type": "enum (memory_t1, memory_t2, memory_t3, external_api, graph_node, bq_table)",
  "resource_id": "string (specific reference: node_id, table_name, api_endpoint)",
  "request_context": {
    "http_method": "string (GET, POST, PATCH, DELETE)",
    "url": "string (redacted of credentials)",
    "headers_count": "integer (how many headers; full headers NOT logged for privacy)"
  },
  "response_context": {
    "http_status_code": "integer (or null if non-HTTP)",
    "response_size_bytes": "integer",
    "latency_ms": "integer"
  },
  "outcome": "enum (success, permission_denied, not_found, timeout, error, fallback)",
  "error_details": {
    "error_type": "string (optional; exception class name if error)",
    "error_message": "string (optional; redacted message; no secrets)"
  },
  "evidence_metrics": {
    "nodes_traversed": "integer (for graph queries)",
    "rows_scanned": "integer (for BQ queries)",
    "tokens_used": "integer (for LLM calls)",
    "evidence_weight": "numeric (confidence of result; 0.0–1.0)"
  },
  "trace_id": "string (Cloud Trace correlation ID)",
  "parent_event_id": "UUID (optional; event that triggered this one)",
  "idempotency_key": "string (optional; for idempotent retry detection)"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `event_id` | UUID | ✓ | Unique; generated at write time |
| `event_timestamp_utc` | RFC3339 | ✓ | Exact moment of event in UTC |
| `campaign_id` | string | ✓ | Scope to campaign; enables easy filtering and cleanup |
| `run_id` | string | ✓ | Link to specific benchmark run |
| `event_type` | enum | ✓ | See §2.2 for valid types |
| `agent_id` | string | ✓ | Which agent performed action; traced to E2-T2 profile |
| `tenant_id` | string | ✓ | For campaign: always `amg-campaign-svc` |
| `severity` | enum | ✓ | INFO (normal), WARN (unusual but handled), ERROR (action failed), CRITICAL (system threat) |
| `action` | string | ✓ | Specific action attempted (e.g., "read_t1", "write_t2", "api_call_github") |
| `resource_type` | enum | ✓ | What was accessed (memory tier, external service, data) |
| `resource_id` | string | ✓ | Specific reference (node ID, table name, URL, etc.) |
| `request_context.http_method` | string | ✗ | HTTP method if applicable; null for non-HTTP |
| `request_context.url` | string | ✗ | URL with query params redacted; no auth tokens |
| `request_context.headers_count` | int | ✓ | Count only (privacy: full headers not logged) |
| `response_context.http_status_code` | int | ✗ | HTTP status; null if non-HTTP or pending |
| `response_context.response_size_bytes` | int | ✓ | Payload size; enables cost attribution |
| `response_context.latency_ms` | int | ✓ | Wall-clock time for operation |
| `outcome` | enum | ✓ | success, permission_denied, not_found, timeout, error, fallback |
| `error_details.error_type` | string | ✗ | Exception class if error; null otherwise |
| `error_details.error_message` | string | ✗ | User-safe message; no stack traces or secrets |
| `evidence_metrics.nodes_traversed` | int | ✓ | Graph query complexity metric |
| `evidence_metrics.rows_scanned` | int | ✓ | BigQuery cost proxy |
| `evidence_metrics.tokens_used` | int | ✓ | LLM token consumption |
| `evidence_metrics.evidence_weight` | numeric | ✓ | Confidence (0.0–1.0) for retrieved evidence |
| `trace_id` | string | ✓ | Correlation ID for distributed tracing (Cloud Trace) |
| `parent_event_id` | UUID | ✗ | If this event was caused by another event; enables causality chain |
| `idempotency_key` | string | ✗ | If applicable (for idempotent API retry detection) |

---

### 2.2 Valid Event Types

| Event Type | Agent | Resource | Typical Outcome | Example |
|-----------|-------|----------|-----------------|---------|
| `agent_invoked` | any | T1 | success | Agent received query; context loaded |
| `t1_context_loaded` | any | memory_t1 | success | T1 context fetched from session |
| `t2_retrieval_attempt` | any | memory_t2 | success / not_found | Graph query executed; nodes returned |
| `t2_write_attempt` | TA/CA | memory_t2 | success / permission_denied | Graph edge created (e.g., task assignment) |
| `t3_audit_append` | any | memory_t3 | success | This audit event written to T3 |
| `external_api_call` | SI/CM/CA | external_api | success / timeout / error | Slack/Calendar/GitHub API invoked |
| `bq_query_executed` | any | bq_table | success / timeout / error | BigQuery query run; rows returned |
| `corpus_retrieval` | any | corpus | success / not_found | Corpus document fetched from GCS |
| `llm_inference_start` | any | llm_service | success | Inference request sent to Vertex AI |
| `llm_inference_end` | any | llm_service | success / error | Inference completed; tokens counted |
| `evidence_aggregation` | any | n/a | success | Evidence from multiple sources combined |
| `response_generation` | any | n/a | success | Agent response synthesized for user |
| `scoring_event` | auto/MLE | benchmark_metrics | success | Run scored (task_success, groundedness) |
| `fallback_triggered` | any | n/a | success | Fallback strategy activated (e.g., timeout recovery) |
| `error_recovery` | any | n/a | success / error | Error handling executed |

---

## 3. Cloud Trace Integration

**Tool:** Google Cloud Trace (built-in to GCP); no external dependency.

### 3.1 Trace Structure

Each run generates a **single trace** with multiple **spans**:

```
trace_id: <UUID from run manifest>
  └─ span: agent_execution (root)
      ├─ span: retrieval_phase
      │   ├─ span: graph_query (latency_ms from E4-T3)
      │   ├─ span: bq_query (latency_ms)
      │   └─ span: corpus_retrieval (latency_ms)
      ├─ span: inference_phase
      │   └─ span: vertex_ai_call (latency_ms)
      └─ span: response_synthesis
          └─ span: scoring (latency_ms)
```

### 3.2 Trace Span Schema

```json
{
  "trace_id": "string (from run manifest)",
  "span_id": "string (unique within trace)",
  "parent_span_id": "string (optional; parent in trace hierarchy)",
  "display_name": "string (human-readable; e.g., 'bq_query')",
  "start_time": "RFC3339",
  "end_time": "RFC3339",
  "duration_ms": "integer (end_time - start_time)",
  "attributes": {
    "http.method": "string (if HTTP)",
    "http.url": "string (redacted)",
    "http.status_code": "integer (if HTTP)",
    "db.type": "string ('spanner', 'bigquery', or null)",
    "db.statement": "string (query text; only for deterministic/template queries)",
    "rpc.method": "string (if RPC call, e.g., 'Vertex AI InferenceService/Predict')",
    "error": "boolean (true if span ended in error)",
    "error.type": "string (exception type if error)"
  },
  "events": [
    {
      "name": "string (e.g., 'result_received', 'timeout', 'retry')",
      "timestamp": "RFC3339",
      "attributes": {
        "result_count": "integer",
        "attempt_number": "integer (if retry)"
      }
    }
  ]
}
```

---

## 4. BigQuery Agent Analytics Table

**Purpose:** Aggregated execution statistics for dashboard and KPI computation.

### 4.1 Agent Analytics Schema

```sql
CREATE OR REPLACE TABLE `{{PROJECT_ID}}.benchmark_metrics.agent_analytics` (
  -- Identity
  analytics_id STRING NOT NULL,
  run_id STRING NOT NULL,
  campaign_id STRING NOT NULL,
  scenario_id STRING NOT NULL,
  agent_id STRING NOT NULL,
  execution_timestamp_utc TIMESTAMP NOT NULL,

  -- Execution Summary
  total_latency_ms INT64 NOT NULL,
  retrieval_latency_pct NUMERIC(3, 1) NOT NULL,  -- % of total
  inference_latency_pct NUMERIC(3, 1) NOT NULL,
  api_latency_pct NUMERIC(3, 1) NOT NULL,

  -- Evidence Retrieval
  graph_nodes_traversed INT64 NOT NULL,
  graph_traversal_hops INT64 NOT NULL,
  bq_rows_scanned INT64 NOT NULL,
  corpus_docs_retrieved INT64 NOT NULL,
  avg_retrieval_relevance_score NUMERIC(3, 2) NOT NULL,

  -- Token and Cost Metrics
  input_tokens INT64 NOT NULL,
  output_tokens INT64 NOT NULL,
  total_tokens INT64 NOT NULL,
  cost_usd NUMERIC(7, 4) NOT NULL,
  tokens_per_ms NUMERIC(7, 3) NOT NULL,  -- efficiency metric

  -- Evidence Quality
  evidence_sources_used INT64 NOT NULL,  -- distinct (graph, bq, corpus)
  evidence_weight_avg NUMERIC(3, 2) NOT NULL,  -- avg confidence
  evidence_weight_min NUMERIC(3, 2) NOT NULL,  -- worst piece of evidence

  -- Error Tracking
  errors_encountered INT64 NOT NULL,  -- count
  fallback_activated BOOL NOT NULL,
  fallback_strategy_name STRING,

  -- Scoring Results (cached from E4-T3 run manifest)
  task_success BOOL NOT NULL,
  groundedness_score NUMERIC(3, 2) NOT NULL,

  -- Audit Linkage
  audit_event_count INT64 NOT NULL,
  audit_event_ids ARRAY<STRING> NOT NULL,
  trace_id STRING NOT NULL,

  PRIMARY KEY (analytics_id),
  CONSTRAINT retrieval_latency_pct_valid CHECK (retrieval_latency_pct >= 0 AND retrieval_latency_pct <= 100),
  CONSTRAINT inference_latency_pct_valid CHECK (inference_latency_pct >= 0 AND inference_latency_pct <= 100),
  CONSTRAINT api_latency_pct_valid CHECK (api_latency_pct >= 0 AND api_latency_pct <= 100)
) PARTITION BY DATE(execution_timestamp_utc)
CLUSTER BY campaign_id, agent_id, scenario_id;
```

---

## 5. Observability Capture Points

| Capture Point | Event Type | Trigger | Data Captured |
|--------------|-----------|---------|----------------|
| **T1 Load** | t1_context_loaded | Context fetched at start of agent invocation | session_id, context_size_bytes, latency_ms |
| **T2 Query** | t2_retrieval_attempt | Agent queries graph for evidence | node_ids_retrieved, hops, latency_ms, relevance_scores |
| **T2 Write** | t2_write_attempt | Agent creates graph edge (TA/CA only) | edge_label, source_id, target_id, audit_event_id |
| **T3 Append** | t3_audit_append | Audit event written (every event triggers this) | event_id, campaign_id, run_id, latency_ms (should be <10ms) |
| **BQ Query** | bq_query_executed | BigQuery query executed | query_hash, rows_scanned, latency_ms, cost_usd |
| **Corpus Fetch** | corpus_retrieval | GCS document fetched from corpus | doc_id, corpus_type, doc_size_bytes, relevance_score |
| **API Call** | external_api_call | Slack/Calendar/GitHub/Jira invoked | api_endpoint, http_status, latency_ms, response_size_bytes |
| **LLM Start** | llm_inference_start | Inference request sent to Vertex AI | model_name, input_tokens, trace_id |
| **LLM End** | llm_inference_end | Inference completed; response received | output_tokens, latency_ms, model_version |
| **Evidence Aggregation** | evidence_aggregation | Multiple evidence sources combined | sources_count, final_weight, confidence_threshold_met |
| **Response Synthesis** | response_generation | Agent response composed and delivered to user | response_length_chars, response_latency_ms |
| **Scoring** | scoring_event | Run scored after execution complete | task_success, groundedness_score, scorer_id |

---

## 6. Observability Dashboard (Grafana / Data Studio)

**Proposed visualizations:**

1. **Success Rate by Scenario** — bar chart; success_rate % on Y, scenario_id on X
2. **Groundedness Distribution** — histogram; groundedness_score [0.0–1.0] on X, frequency on Y
3. **Latency Breakdown** — stacked bar chart; retrieval / inference / api % per scenario
4. **Cost Trend** — line chart; cumulative cost_usd over time; show budget cap (USD 300) and hard stop (USD 260)
5. **Evidence Quality** — scatter plot; nodes_traversed (X) vs. groundedness_score (Y); identify sweet spot
6. **Error Rate by Agent** — table; agent_id, error_count, error_pct, most common error_type
7. **Audit Event Timeline** — waterfall; show sequence of events for a single run; latency between stages

---

## 7. No-Evidence Observability

If agent returns no-evidence abstention (from E4-T1):

| Field | Value |
|-------|-------|
| `outcome` | "success" (no-evidence is a valid outcome, not an error) |
| `severity` | "INFO" |
| `evidence_weight` | 0.0 (no evidence retrieved) |
| `nodes_traversed` | 0 (graph returned empty) |
| `rows_scanned` | 0 (BQ returned no rows) |
| `corpus_docs_retrieved` | 0 |
| `groundedness_score` | 1.0 (perfect grounding in absence of evidence) |
| `task_success` | true or false depending on scenario (see E4-T2) |

**Audit log shows:** "No evidence found for query X; agent abstained; grounding is 100% in null evidence"

---

## 8. Observability Validation Checklist (E4-T7 Dry-Run)

| Item | Status | Notes |
|------|--------|-------|
| ☐ Every run produces exactly one T3 audit root event | | Check: count(distinct event_id) == count(distinct run_id) |
| ☐ Every T3 event has valid event_type from §2.2 | | Schema validation + enum check |
| ☐ Every run has exactly one trace_id in Cloud Trace | | Verify: trace_id in run manifest matches Cloud Trace |
| ☐ Trace spans have valid parent/child relationships | | DAG validation; no cycles |
| ☐ BigQuery analytics table row count matches run count | | count(agent_analytics) == count(runs) |
| ☐ Latency breakdown percentages sum to 100% (±1%) | | retrieval_pct + inference_pct + api_pct ≈ 100 |
| ☐ Audit events are immutable (no UPDATE/DELETE on T3) | | Verify: all rows have created_at; no modified_at |
| ☐ No secrets in audit event URLs or error messages | | Scan error_details.error_message for auth tokens; reject if found |
| ☐ Cloud Trace retention compliant (30 days auto-cleanup) | | GCP Cloud Trace default; verify no manual ops needed |
