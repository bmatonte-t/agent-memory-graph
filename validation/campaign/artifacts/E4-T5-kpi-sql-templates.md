# E4-T5 — KPI SQL Templates and Formulas

**Epic:** E4 — Benchmark, Observability, and Cost Control Design
**Task:** E4-T5
**Date:** 2026-07-08
**Status:** Approved
**Owner:** Analytics Lead

---

## 1. KPI Calculation Methodology

All KPIs are computed from the `benchmark_metrics.runs` table (E4-T3) and `benchmark_metrics.agent_analytics` table (E4-T4).

- **Primary KPIs** (tied to go/no-go decision): success_rate, avg_groundedness
- **Diagnostic KPIs** (help interpret results): latency_p99, cost_per_run, fallback_rate
- **Quality KPIs** (assess hidden risks): evidence_quality_score, error_rate_by_type

---

## 2. Primary KPIs

### 2.1 Overall Success Rate

**Definition:** Fraction of runs where task_success = true.

```sql
SELECT
  ROUND(
    SUM(CAST(task_success AS INT64)) / COUNT(*),
    3
  ) AS success_rate
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
ORDER BY success_rate DESC;
```

**Threshold:** ≥ 0.75 (acceptable), ≥ 0.85 (goal)

---

### 2.2 Success Rate by Scenario

```sql
SELECT
  scenario_id,
  COUNT(*) AS total_runs,
  SUM(CAST(task_success AS INT64)) AS successes,
  ROUND(
    SUM(CAST(task_success AS INT64)) / COUNT(*),
    3
  ) AS scenario_success_rate
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
GROUP BY scenario_id
ORDER BY scenario_success_rate DESC, scenario_id;
```

---

### 2.3 Success Rate by Agent

```sql
SELECT
  agent_id,
  COUNT(*) AS total_runs,
  SUM(CAST(task_success AS INT64)) AS successes,
  ROUND(
    SUM(CAST(task_success AS INT64)) / COUNT(*),
    3
  ) AS agent_success_rate
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
GROUP BY agent_id
ORDER BY agent_success_rate DESC, agent_id;
```

---

### 2.4 Overall Average Groundedness

**Definition:** Mean groundedness_score across all measured runs.

```sql
SELECT
  ROUND(AVG(groundedness_score), 3) AS avg_groundedness,
  ROUND(STDDEV(groundedness_score), 3) AS stddev_groundedness,
  ROUND(MIN(groundedness_score), 3) AS min_groundedness,
  ROUND(MAX(groundedness_score), 3) AS max_groundedness,
  APPROX_QUANTILES(groundedness_score, 100)[OFFSET(50)] AS median_groundedness
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false;
```

**Threshold:** avg ≥ 0.75 (acceptable), ≥ 0.85 (goal)

---

### 2.5 Average Groundedness by Scenario

```sql
SELECT
  scenario_id,
  COUNT(*) AS runs,
  ROUND(AVG(groundedness_score), 3) AS avg_groundedness,
  ROUND(STDDEV(groundedness_score), 3) AS stddev,
  APPROX_QUANTILES(groundedness_score, 100)[OFFSET(25)] AS p25,
  APPROX_QUANTILES(groundedness_score, 100)[OFFSET(75)] AS p75
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
GROUP BY scenario_id
ORDER BY avg_groundedness DESC, scenario_id;
```

---

### 2.6 Campaign Score (Primary Metric)

**Definition:** Equal-weight average of success_rate and avg_groundedness.

$$\text{Campaign Score} = \frac{1}{2} \times \text{success\_rate} + \frac{1}{2} \times \text{avg\_groundedness}$$

```sql
WITH campaign_rates AS (
  SELECT
    SUM(CAST(task_success AS INT64)) / COUNT(*) AS success_rate,
    AVG(groundedness_score) AS avg_groundedness
  FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
  WHERE campaign_id = '{{CAMPAIGN_ID}}'
    AND warmup_flag = false
)
SELECT
  ROUND(success_rate, 3) AS success_rate,
  ROUND(avg_groundedness, 3) AS avg_groundedness,
  ROUND((success_rate + avg_groundedness) / 2, 3) AS campaign_score
FROM campaign_rates;
```

**Threshold:** ≥ 0.75 (acceptable), ≥ 0.85 (goal)

---

## 3. Diagnostic KPIs

### 3.1 End-to-End Latency Percentiles

```sql
SELECT
  scenario_id,
  COUNT(*) AS runs,
  ROUND(AVG(latency_total_ms), 1) AS mean_latency_ms,
  ROUND(APPROX_QUANTILES(latency_total_ms, 100)[OFFSET(50)], 1) AS p50_latency_ms,
  ROUND(APPROX_QUANTILES(latency_total_ms, 100)[OFFSET(90)], 1) AS p90_latency_ms,
  ROUND(APPROX_QUANTILES(latency_total_ms, 100)[OFFSET(99)], 1) AS p99_latency_ms,
  MAX(latency_total_ms) AS max_latency_ms
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
GROUP BY scenario_id
ORDER BY p99_latency_ms DESC, scenario_id;
```

**Expected:** Most scenarios <10s; EMC-011 (calendar) and EMC-012 (PR summary) may reach 15–20s.

---

### 3.2 Latency Breakdown (Retrieval vs. Inference vs. API)

```sql
SELECT
  agent_id,
  COUNT(*) AS runs,
  ROUND(AVG(latency_retrieval_ms), 1) AS avg_retrieval_ms,
  ROUND(AVG(latency_inference_ms), 1) AS avg_inference_ms,
  ROUND(AVG(latency_external_api_ms), 1) AS avg_api_ms,
  ROUND(
    100 * SUM(latency_retrieval_ms) / SUM(latency_total_ms),
    1
  ) AS retrieval_pct,
  ROUND(
    100 * SUM(latency_inference_ms) / SUM(latency_total_ms),
    1
  ) AS inference_pct,
  ROUND(
    100 * SUM(latency_external_api_ms) / SUM(latency_total_ms),
    1
  ) AS api_pct
FROM `{{PROJECT_ID}}.benchmark_metrics.agent_analytics`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND fallback_activated = false
GROUP BY agent_id
ORDER BY retrieval_pct DESC, agent_id;
```

---

### 3.3 Cost Per Run

```sql
SELECT
  scenario_id,
  agent_id,
  COUNT(*) AS runs,
  ROUND(SUM(estimated_cost_usd), 4) AS total_cost_usd,
  ROUND(AVG(estimated_cost_usd), 6) AS avg_cost_per_run_usd,
  ROUND(MIN(estimated_cost_usd), 6) AS min_cost_usd,
  ROUND(MAX(estimated_cost_usd), 6) AS max_cost_usd,
  ROUND(STDDEV(estimated_cost_usd), 6) AS stddev_cost_usd
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
GROUP BY scenario_id, agent_id
ORDER BY total_cost_usd DESC, scenario_id, agent_id;
```

**Budget context:** 360 measured runs × ~$0.01/run avg (Flash model) ≈ $3.60 total run cost; Weeks 4-6 exploratory runs may add more.

---

### 3.4 Token Efficiency

```sql
SELECT
  agent_id,
  COUNT(*) AS runs,
  ROUND(AVG(total_tokens), 0) AS avg_tokens_per_run,
  ROUND(AVG(input_tokens), 0) AS avg_input_tokens,
  ROUND(AVG(output_tokens), 0) AS avg_output_tokens,
  ROUND(AVG(input_tokens) / NULLIF(AVG(output_tokens), 0), 2) AS input_output_ratio,
  ROUND(AVG(total_tokens) / NULLIF(AVG(latency_total_ms), 0) * 1000, 2) AS tokens_per_second
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
GROUP BY agent_id
ORDER BY tokens_per_second DESC, agent_id;
```

---

## 4. Quality KPIs

### 4.1 Evidence Quality Score

**Definition:** Weighted average of retrieval quality signals.

$$\text{Evidence Quality} = 0.3 \times \text{avg\_relevance} + 0.4 \times \text{source\_diversity} + 0.3 \times \text{confidence}$$

```sql
WITH evidence_stats AS (
  SELECT
    run_id,
    ROUND(AVG(relevance_score), 3) AS avg_relevance,
    COUNT(DISTINCT source) AS source_diversity,
    ROUND(AVG(evidence_weight), 3) AS avg_confidence
  FROM `{{PROJECT_ID}}.benchmark_metrics.runs`,
    UNNEST(retrieved_docs) AS doc
  WHERE campaign_id = '{{CAMPAIGN_ID}}'
    AND warmup_flag = false
  GROUP BY run_id
)
SELECT
  ROUND(AVG(0.3 * avg_relevance + 0.4 * MIN(source_diversity, 3) / 3 + 0.3 * avg_confidence), 3)
    AS avg_evidence_quality_score
FROM evidence_stats;
```

**Interpretation:** Score near 1.0 indicates high-quality evidence; <0.5 indicates weak grounding.

---

### 4.2 Fallback Rate

**Definition:** Fraction of runs where fallback_used = true.

```sql
SELECT
  ROUND(
    SUM(CAST(fallback_used AS INT64)) / COUNT(*),
    3
  ) AS fallback_rate,
  COUNTIF(fallback_used = true) AS fallback_count,
  COUNT(*) AS total_runs
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false;
```

**Acceptable:** ≤ 5% (no more than 18 runs out of 360)

---

### 4.3 Error Rate by Type

```sql
SELECT
  error_type,
  COUNT(*) AS error_count,
  ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS error_pct
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
  AND error_occurred = true
GROUP BY error_type
ORDER BY error_count DESC;
```

---

### 4.4 No-Evidence Handling

**Definition:** Fraction of runs where agent returned safe abstention (no-evidence).

```sql
SELECT
  scenario_id,
  COUNTIF(error_type = 'no_evidence') AS no_evidence_count,
  ROUND(
    100 * COUNTIF(error_type = 'no_evidence') / COUNT(*),
    2
  ) AS no_evidence_pct,
  COUNTIF(error_type = 'no_evidence' AND task_success = true) AS correct_abstentions
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
GROUP BY scenario_id
ORDER BY no_evidence_pct DESC, scenario_id;
```

---

## 5. Scenario-Specific KPIs

### 5.1 Data Isolation Quality (EMC-004)

```sql
SELECT
  scenario_id,
  COUNT(*) AS runs,
  COUNTIF(task_success = true) AS isolation_passes,
  ROUND(100 * COUNTIF(task_success = true) / COUNT(*), 2) AS isolation_success_pct
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
  AND scenario_id = 'EMC-004'
GROUP BY scenario_id;
```

---

### 5.2 Multi-Source Grounding Quality (EMC-006)

```sql
SELECT
  scenario_id,
  COUNT(*) AS runs,
  ROUND(AVG(groundedness_score), 3) AS avg_groundedness,
  APPROX_QUANTILES(groundedness_score, 100)[OFFSET(90)] AS p90_groundedness,
  COUNTIF(groundedness_score >= 0.80) AS high_grounding_runs
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
  AND scenario_id = 'EMC-006'
GROUP BY scenario_id;
```

---

### 5.3 External API Integration Success (SI/CM/CA)

```sql
SELECT
  agent_id,
  scenario_id,
  COUNT(*) AS total_runs,
  COUNTIF(task_success = true) AS api_successes,
  COUNTIF(error_type = 'api_error') AS api_errors,
  ROUND(100 * COUNTIF(task_success = true) / COUNT(*), 2) AS api_integration_success_pct,
  ROUND(AVG(latency_external_api_ms), 1) AS avg_external_latency_ms
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
  AND agent_id IN ('AGENT-SI', 'AGENT-CM', 'AGENT-CA')
GROUP BY agent_id, scenario_id
ORDER BY api_integration_success_pct DESC;
```

---

## 6. Validation and Audit Queries

### 6.1 Data Completeness Check

```sql
SELECT
  COUNT(*) AS total_rows,
  COUNTIF(run_id IS NOT NULL) AS has_run_id,
  COUNTIF(task_success IS NOT NULL) AS has_task_success,
  COUNTIF(groundedness_score IS NOT NULL) AS has_groundedness,
  COUNTIF(estimated_cost_usd IS NOT NULL) AS has_cost,
  COUNTIF(warmup_flag = false) AS measured_runs
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}';
```

**Expected for full campaign:** measured_runs = 360 (12 scenarios × 30 runs each)

---

### 6.2 Cost Ledger Reconciliation

```sql
SELECT
  'benchmark_metrics.runs' AS source,
  SUM(estimated_cost_usd) AS total_cost_from_runs
FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND warmup_flag = false
UNION ALL
SELECT
  'benchmark_metrics.agent_analytics' AS source,
  SUM(cost_usd) AS total_cost_from_analytics
FROM `{{PROJECT_ID}}.benchmark_metrics.agent_analytics`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
ORDER BY source;
```

**Expected:** Both sources report same total (or within 0.1% due to rounding)

---

## 7. KPI Refresh Cadence

| KPI | Refresh Frequency | Owner | Automation |
|-----|------------------|-------|-----------|
| Primary (Success Rate, Groundedness, Campaign Score) | Every 4 hours (during Week 5 execution) | Analytics Lead | Cloud Scheduler → BigQuery job |
| Diagnostic (Latency, Cost, Token Efficiency) | Daily | Analytics Lead | Automated query → Data Studio |
| Quality (Evidence, Fallback, Error Rate) | Daily | MLE Lead | Automated query + manual review |
| Scenario-Specific | Daily | Respective agent owner | Automated query |
| Validation (Completeness, Cost Reconciliation) | Every 12 hours | Infrastructure Lead | Automated query + alert on drift |

---

## 8. KPI Template Variables

All KPI queries use these template variables (resolved at execution time):
- `{{PROJECT_ID}}` — GCP project ID (from E1-T3)
- `{{CAMPAIGN_ID}}` — Campaign identifier (amg-campaign-2026-06-29)
- `{{WEEK}}` — Execution week (4, 5, or 6)

Substitute before running any query.
