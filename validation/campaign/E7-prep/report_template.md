# Cognitive Agent Memory Graph — Benchmark Validation Report
# Template version: v1.0 | Populate during E8-T3 after E7-exec completes
# Placeholders: {{VARIABLE}} format — replace with actual values from benchmark_metrics tables

**Campaign ID:** amg-campaign-2026-06-29
**Validation Period:** 2026-07-23 to 2026-07-27
**Report Date:** {{REPORT_DATE}}
**Prepared by:** {{REPORT_AUTHOR}}
**Classification:** Campaign-Internal → Stakeholder Distribution

---

## Executive Summary

The Cognitive Agent Memory Graph (AMG) validation campaign executed {{TOTAL_RUNS}} measured benchmark runs across {{SCENARIO_COUNT}} scenarios between 2026-07-23 and 2026-07-27 on Google Cloud Platform project `amg-validation-2026-07-q3`.

**Overall Recommendation:** {{GO_NOGO_DECISION}} — {{RECOMMENDATION_RATIONALE}}

| KPI | Result | Target (Plan §13) | Status |
|-----|--------|-------------------|--------|
| Overall Success Rate | {{SUCCESS_RATE}} | ≥ 85% (CI lower ≥ 80%) | {{SUCCESS_STATUS}} |
| Average Groundedness | {{AVG_GROUNDEDNESS}} | ≥ 0.90 (CI lower ≥ 0.85) | {{GROUNDEDNESS_STATUS}} |
| Latency p95 | {{P95_LATENCY_MS}}ms | ≤ 10,000ms | {{LATENCY_STATUS}} |
| Cost per Run | ${{COST_PER_RUN}} | ≤ $0.05 | {{COST_STATUS}} |
| System Reliability | {{RELIABILITY_PCT}}% | ≥ 95% | {{RELIABILITY_STATUS}} |
| Total Campaign Cost | ${{TOTAL_COST}} | ≤ $260 (hard stop) | {{TOTAL_COST_STATUS}} |

**Key Findings:**
1. {{KEY_FINDING_1}}
2. {{KEY_FINDING_2}}
3. {{KEY_FINDING_3}}

---

## 1. Campaign Configuration (Frozen — E6-T7)

| Component | Configuration | Frozen Since |
|-----------|---------------|-------------|
| GCP Project | amg-validation-2026-07-q3 | E5-T1 |
| Spanner Instance | amg-campaign-spanner (multi-region-us, 1 node) | E5-T8 |
| Spanner Database | memory_db (11 migrations) | E6-T3 |
| BigQuery Datasets | raw_retail_public, curated_retail_campaign, benchmark_metrics | E6-T1 |
| GCS Corpus | 2,400 documents, 26 MB, 4 categories | E6-T2 |
| Cloud Run Service | amg-campaign-agents (sha256:{{IMAGE_DIGEST}}) | E6-T7 |
| Agents | AGENT-EC, AGENT-CC, AGENT-TA, AGENT-SI, AGENT-CM, AGENT-CA | E2-T2 |
| Scenarios | EMC-001 through EMC-012 | E4-T1 |
| Runs per Scenario | 30 measured + 5 warmup | E4-T1 |
| Graph Nodes Seeded | 239 (tripartite: T1/T2/T3) | E6-T3 |
| Graph Edges Seeded | ~508 | E6-T3 |

---

## 2. Execution Summary

### 2.1 Run Volume

| Category | Count | Notes |
|----------|-------|-------|
| Total Runs Scheduled | {{TOTAL_SCHEDULED}} | 12 scenarios × 35 (30 measured + 5 warmup) |
| Total Runs Completed | {{TOTAL_COMPLETED}} | Includes warmup |
| Measured Runs | {{MEASURED_RUNS}} | Excludes warmup |
| Warmup Runs | {{WARMUP_RUNS}} | Not counted in KPIs |
| Failed / Errored Runs | {{FAILED_RUNS}} | System errors (see §4.3) |
| Reruns Executed | {{RERUN_COUNT}} | Per failure taxonomy (E7-prep-T7) |
| Extended Scenario Runs | {{EXTENDED_RUNS}} | If budget permitted |

### 2.2 Execution Timeline

| Event | Timestamp | Notes |
|-------|-----------|-------|
| Infrastructure Validation Complete | {{INFRA_VALIDATION_TIMESTAMP}} | E7-exec-T1 |
| Observability Deployed | {{OBSERVABILITY_TIMESTAMP}} | E7-exec-T2 |
| First Benchmark Run | {{FIRST_RUN_TIMESTAMP}} | E7-exec-T3 |
| Last Benchmark Run | {{LAST_RUN_TIMESTAMP}} | E7-exec-T3 |
| Cost Hard-Stop Triggered? | {{HARD_STOP_TRIGGERED}} | If yes, see §4.4 |
| Final Gate Completed | {{GATE_TIMESTAMP}} | E7-exec-T9 |

---

## 3. KPI Results

### 3.1 Success Rate

**Overall:** {{SUCCESS_RATE}} ({{SUCCESS_COUNT}}/{{MEASURED_RUNS}} runs)

| Scenario | Runs | Successes | Success Rate | Pass/Fail |
|----------|------|-----------|-------------|-----------|
| EMC-001 | {{EMC001_N}} | {{EMC001_SUCCESS}} | {{EMC001_RATE}} | {{EMC001_PASS}} |
| EMC-002 | {{EMC002_N}} | {{EMC002_SUCCESS}} | {{EMC002_RATE}} | {{EMC002_PASS}} |
| EMC-003 | {{EMC003_N}} | {{EMC003_SUCCESS}} | {{EMC003_RATE}} | {{EMC003_PASS}} |
| EMC-004 | {{EMC004_N}} | {{EMC004_SUCCESS}} | {{EMC004_RATE}} | {{EMC004_PASS}} |
| EMC-005 | {{EMC005_N}} | {{EMC005_SUCCESS}} | {{EMC005_RATE}} | {{EMC005_PASS}} |
| EMC-006 | {{EMC006_N}} | {{EMC006_SUCCESS}} | {{EMC006_RATE}} | {{EMC006_PASS}} |
| EMC-007 | {{EMC007_N}} | {{EMC007_SUCCESS}} | {{EMC007_RATE}} | {{EMC007_PASS}} |
| EMC-008 | {{EMC008_N}} | {{EMC008_SUCCESS}} | {{EMC008_RATE}} | {{EMC008_PASS}} |
| EMC-009 | {{EMC009_N}} | {{EMC009_SUCCESS}} | {{EMC009_RATE}} | {{EMC009_PASS}} |
| EMC-010 | {{EMC010_N}} | {{EMC010_SUCCESS}} | {{EMC010_RATE}} | {{EMC010_PASS}} |
| EMC-011 | {{EMC011_N}} | {{EMC011_SUCCESS}} | {{EMC011_RATE}} | {{EMC011_PASS}} |
| EMC-012 | {{EMC012_N}} | {{EMC012_SUCCESS}} | {{EMC012_RATE}} | {{EMC012_PASS}} |

### 3.2 Groundedness Scores

**Overall Average:** {{AVG_GROUNDEDNESS}} (target: ≥ 0.75)

| Scenario | Mean Groundedness | Std Dev | Min | Max | Pass/Fail |
|----------|-----------------|---------|-----|-----|-----------|
| EMC-001 | {{EMC001_GROUND_MEAN}} | {{EMC001_GROUND_STD}} | {{EMC001_GROUND_MIN}} | {{EMC001_GROUND_MAX}} | {{EMC001_GROUND_PASS}} |
| EMC-002 | {{EMC002_GROUND_MEAN}} | {{EMC002_GROUND_STD}} | {{EMC002_GROUND_MIN}} | {{EMC002_GROUND_MAX}} | {{EMC002_GROUND_PASS}} |
| EMC-003 | {{EMC003_GROUND_MEAN}} | {{EMC003_GROUND_STD}} | {{EMC003_GROUND_MIN}} | {{EMC003_GROUND_MAX}} | {{EMC003_GROUND_PASS}} |
| EMC-004 | {{EMC004_GROUND_MEAN}} | {{EMC004_GROUND_STD}} | {{EMC004_GROUND_MIN}} | {{EMC004_GROUND_MAX}} | {{EMC004_GROUND_PASS}} |
| EMC-005 | {{EMC005_GROUND_MEAN}} | {{EMC005_GROUND_STD}} | {{EMC005_GROUND_MIN}} | {{EMC005_GROUND_MAX}} | {{EMC005_GROUND_PASS}} |
| EMC-006 | {{EMC006_GROUND_MEAN}} | {{EMC006_GROUND_STD}} | {{EMC006_GROUND_MIN}} | {{EMC006_GROUND_MAX}} | {{EMC006_GROUND_PASS}} |
| EMC-007 | {{EMC007_GROUND_MEAN}} | {{EMC007_GROUND_STD}} | {{EMC007_GROUND_MIN}} | {{EMC007_GROUND_MAX}} | {{EMC007_GROUND_PASS}} |
| EMC-008 | {{EMC008_GROUND_MEAN}} | {{EMC008_GROUND_STD}} | {{EMC008_GROUND_MIN}} | {{EMC008_GROUND_MAX}} | {{EMC008_GROUND_PASS}} |
| EMC-009 | {{EMC009_GROUND_MEAN}} | {{EMC009_GROUND_STD}} | {{EMC009_GROUND_MIN}} | {{EMC009_GROUND_MAX}} | {{EMC009_GROUND_PASS}} |
| EMC-010 | {{EMC010_GROUND_MEAN}} | {{EMC010_GROUND_STD}} | {{EMC010_GROUND_MIN}} | {{EMC010_GROUND_MAX}} | {{EMC010_GROUND_PASS}} |
| EMC-011 | {{EMC011_GROUND_MEAN}} | {{EMC011_GROUND_STD}} | {{EMC011_GROUND_MIN}} | {{EMC011_GROUND_MAX}} | {{EMC011_GROUND_PASS}} |
| EMC-012 | {{EMC012_GROUND_MEAN}} | {{EMC012_GROUND_STD}} | {{EMC012_GROUND_MIN}} | {{EMC012_GROUND_MAX}} | {{EMC012_GROUND_PASS}} |

### 3.3 Latency Analysis

**p95 Latency Overall:** {{P95_LATENCY_MS}}ms (target: ≤ 10,000ms)

| Scenario | Avg (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Max SLA (ms) | Pass/Fail |
|----------|---------|---------|---------|---------|-------------|-----------|
| EMC-001 | {{EMC001_AVG_LAT}} | {{EMC001_P50_LAT}} | {{EMC001_P95_LAT}} | {{EMC001_P99_LAT}} | 10,000 | {{EMC001_LAT_PASS}} |
| EMC-002 | {{EMC002_AVG_LAT}} | {{EMC002_P50_LAT}} | {{EMC002_P95_LAT}} | {{EMC002_P99_LAT}} | 8,000 | {{EMC002_LAT_PASS}} |
| EMC-003 | {{EMC003_AVG_LAT}} | {{EMC003_P50_LAT}} | {{EMC003_P95_LAT}} | {{EMC003_P99_LAT}} | 5,000 | {{EMC003_LAT_PASS}} |
| EMC-004 | {{EMC004_AVG_LAT}} | {{EMC004_P50_LAT}} | {{EMC004_P95_LAT}} | {{EMC004_P99_LAT}} | 8,000 | {{EMC004_LAT_PASS}} |
| EMC-005 | {{EMC005_AVG_LAT}} | {{EMC005_P50_LAT}} | {{EMC005_P95_LAT}} | {{EMC005_P99_LAT}} | 6,000 | {{EMC005_LAT_PASS}} |
| EMC-006 | {{EMC006_AVG_LAT}} | {{EMC006_P50_LAT}} | {{EMC006_P95_LAT}} | {{EMC006_P99_LAT}} | 12,000 | {{EMC006_LAT_PASS}} |
| EMC-007 | {{EMC007_AVG_LAT}} | {{EMC007_P50_LAT}} | {{EMC007_P95_LAT}} | {{EMC007_P99_LAT}} | 8,000 | {{EMC007_LAT_PASS}} |
| EMC-008 | {{EMC008_AVG_LAT}} | {{EMC008_P50_LAT}} | {{EMC008_P95_LAT}} | {{EMC008_P99_LAT}} | 10,000 | {{EMC008_LAT_PASS}} |
| EMC-009 | {{EMC009_AVG_LAT}} | {{EMC009_P50_LAT}} | {{EMC009_P95_LAT}} | {{EMC009_P99_LAT}} | 8,000 | {{EMC009_LAT_PASS}} |
| EMC-010 | {{EMC010_AVG_LAT}} | {{EMC010_P50_LAT}} | {{EMC010_P95_LAT}} | {{EMC010_P99_LAT}} | 8,000 | {{EMC010_LAT_PASS}} |
| EMC-011 | {{EMC011_AVG_LAT}} | {{EMC011_P50_LAT}} | {{EMC011_P95_LAT}} | {{EMC011_P99_LAT}} | 12,000 | {{EMC011_LAT_PASS}} |
| EMC-012 | {{EMC012_AVG_LAT}} | {{EMC012_P50_LAT}} | {{EMC012_P95_LAT}} | {{EMC012_P99_LAT}} | 15,000 | {{EMC012_LAT_PASS}} |

### 3.4 Cost Analysis

**Total Campaign Cost:** ${{TOTAL_COST}} (hard stop: $260)

| Metric | Value | Notes |
|--------|-------|-------|
| Total Spend | ${{TOTAL_COST}} | All runs including warmup |
| Hard-Stop Triggered? | {{HARD_STOP_TRIGGERED}} | If yes, see §4.4 |
| Average per Measured Run | ${{COST_PER_RUN}} | Measured runs only |
| Flash Model Total | ${{FLASH_TOTAL_COST}} | AGENT-EC, CC, SI, CM |
| Pro Model Total | ${{PRO_TOTAL_COST}} | AGENT-TA, CA |
| BigQuery Query Cost | ${{BQ_COST}} | Estimated from bytes scanned |
| Spanner Operations Cost | ${{SPANNER_COST}} | Estimated from node/edge ops |
| GCS Access Cost | ${{GCS_COST}} | Corpus retrieval |
| Budget Utilization | {{BUDGET_PCT}}% | of $260 hard stop |

---

## 4. Statistical Analysis

### 4.1 Confidence Intervals

| KPI | Point Estimate | 95% CI Lower | 95% CI Upper | Margin of Error | n |
|-----|---------------|-------------|-------------|----------------|---|
| Success Rate | {{SUCCESS_RATE}} | {{SUCCESS_CI_LOWER}} | {{SUCCESS_CI_UPPER}} | ±{{SUCCESS_MOE}} | {{N_MEASURED}} |
| Avg Groundedness | {{AVG_GROUNDEDNESS}} | {{GROUND_CI_LOWER}} | {{GROUND_CI_UPPER}} | ±{{GROUND_MOE}} | {{N_MEASURED}} |
| Avg Latency (ms) | {{AVG_LATENCY}} | {{LAT_CI_LOWER}} | {{LAT_CI_UPPER}} | ±{{LAT_MOE}} | {{N_MEASURED}} |

### 4.2 Baseline Comparison (Agent Memory vs. Direct BQ Query)

| Scenario | AMG Success Rate | Baseline Success Rate | Δ | Cohen's d | Significant? |
|----------|-----------------|----------------------|---|-----------|-------------|
| EMC-001 | {{EMC001_AMG_RATE}} | {{EMC001_BASE_RATE}} | {{EMC001_DELTA}} | {{EMC001_D}} | {{EMC001_SIG}} |
| EMC-002 | {{EMC002_AMG_RATE}} | {{EMC002_BASE_RATE}} | {{EMC002_DELTA}} | {{EMC002_D}} | {{EMC002_SIG}} |
| EMC-003 | {{EMC003_AMG_RATE}} | {{EMC003_BASE_RATE}} | {{EMC003_DELTA}} | {{EMC003_D}} | {{EMC003_SIG}} |
| EMC-004 | {{EMC004_AMG_RATE}} | {{EMC004_BASE_RATE}} | {{EMC004_DELTA}} | {{EMC004_D}} | {{EMC004_SIG}} |
| EMC-005 | {{EMC005_AMG_RATE}} | {{EMC005_BASE_RATE}} | {{EMC005_DELTA}} | {{EMC005_D}} | {{EMC005_SIG}} |

### 4.3 Failure Analysis

| Failure Category | Count | % of Total Runs | Rerun Eligible | Reruns Executed |
|-----------------|-------|-----------------|----------------|-----------------|
| Retrieval Timeout | {{TIMEOUT_COUNT}} | {{TIMEOUT_PCT}}% | Yes | {{TIMEOUT_RERUNS}} |
| Inference Error | {{INFERENCE_ERR_COUNT}} | {{INFERENCE_ERR_PCT}}% | No | 0 |
| Task Failure (grounding < 0.5) | {{TASK_FAIL_COUNT}} | {{TASK_FAIL_PCT}}% | Case-by-case | {{TASK_FAIL_RERUNS}} |
| Integration Error | {{INT_ERR_COUNT}} | {{INT_ERR_PCT}}% | Yes | {{INT_ERR_RERUNS}} |
| Cost Hard-Stop | {{HARD_STOP_COUNT}} | {{HARD_STOP_PCT}}% | No | 0 |
| Unknown Error | {{UNKNOWN_COUNT}} | {{UNKNOWN_PCT}}% | No | 0 |

### 4.4 Hard-Stop Events (if applicable)

{{HARD_STOP_SECTION_PLACEHOLDER}}
_If no hard-stop was triggered, this section reads: "No hard-stop events were triggered during E7-exec. Final cumulative spend was ${{TOTAL_COST}}, below the $260 threshold."_

---

## 5. Risk Assessment

### 5.1 Identified Risks and Mitigations

| Risk | Severity | Likelihood | Evidence | Mitigation |
|------|----------|-----------|---------|-----------|
| {{RISK_1}} | {{RISK_1_SEV}} | {{RISK_1_LIKE}} | {{RISK_1_EVIDENCE}} | {{RISK_1_MITIGATION}} |
| {{RISK_2}} | {{RISK_2_SEV}} | {{RISK_2_LIKE}} | {{RISK_2_EVIDENCE}} | {{RISK_2_MITIGATION}} |
| {{RISK_3}} | {{RISK_3_SEV}} | {{RISK_3_LIKE}} | {{RISK_3_EVIDENCE}} | {{RISK_3_MITIGATION}} |

### 5.2 Residual Risks (Post-Campaign)

1. **{{RESIDUAL_RISK_1}}** — Mitigation: {{RESIDUAL_MITIGATION_1}}
2. **{{RESIDUAL_RISK_2}}** — Mitigation: {{RESIDUAL_MITIGATION_2}}

---

## 6. Go / No-Go Recommendation

### 6.1 Decision Matrix

| Acceptance Criterion | Target (Plan §13) | Result | Pass/Fail | Weight |
|---------------------|-------------------|--------|-----------|--------|
| Overall success rate ≥ 85% | ≥ 0.85 | {{SUCCESS_RATE}} | {{SR_PASS}} | P0 |
| Success rate 95% CI lower ≥ 80% | ≥ 0.80 | {{SUCCESS_CI_LOWER}} | {{SR_CI_PASS}} | P0 |
| Average groundedness ≥ 0.90 | ≥ 0.90 | {{AVG_GROUNDEDNESS}} | {{GROUND_PASS}} | P0 |
| Groundedness 95% CI lower ≥ 0.85 | ≥ 0.85 | {{GROUND_CI_LOWER}} | {{GROUND_CI_PASS}} | P0 |
| Latency p95 ≤ 10s | ≤ 10,000ms | {{P95_LATENCY_MS}}ms | {{LAT_PASS}} | P0 |
| System reliability ≥ 95% | ≥ 0.95 | {{RELIABILITY}} | {{REL_PASS}} | P0 |
| Total cost ≤ $260 | ≤ $260 | ${{TOTAL_COST}} | {{COST_PASS}} | P0 |
| No tenant isolation violations | 0 violations | {{ISO_VIOLATIONS}} | {{ISO_PASS}} | P0 |
| ≥ 80% scenarios passing individually | ≥ 80% | {{SCENARIO_PASS_PCT}}% | {{SCEN_PASS}} | P1 |

### 6.2 Final Recommendation

**Decision: {{GO_NOGO_DECISION}}**

_Rationale:_
{{RECOMMENDATION_FULL_TEXT}}

_Residual risk statement:_
{{RESIDUAL_RISK_STATEMENT}}

---

## 7. Appendices

### Appendix A: Raw Run Counts by Scenario
_Source: `benchmark_metrics.runs` WHERE campaign_id='amg-campaign-2026-06-29'_

```sql
-- Populate via E4-T5 SQL template §2.2
SELECT scenario_id, COUNT(*) AS total_runs,
  SUM(CAST(task_success AS INT64)) AS successes,
  ROUND(SUM(CAST(task_success AS INT64)) / COUNT(*), 3) AS scenario_success_rate
FROM `amg-validation-2026-07-q3.benchmark_metrics.runs`
WHERE campaign_id = 'amg-campaign-2026-06-29'
  AND warmup_flag = false
GROUP BY scenario_id ORDER BY scenario_id;
```

### Appendix B: Cost Ledger Summary
_Source: `benchmark_metrics.cost_ledger`_

### Appendix C: Integration Test Results
_Source: E7-exec-T6 failure taxonomy report_

### Appendix D: Observability Dashboard Links
- Benchmark Overview: {{DASHBOARD_OVERVIEW_URL}}
- Cost Control: {{DASHBOARD_COST_URL}}
- Cloud Trace: {{TRACE_URL}}

---

**Report Version:** 1.0
**Template Frozen:** 2026-07-09 (E7-prep-T5)
**Populate During:** E8-T3 (post E7-exec)
