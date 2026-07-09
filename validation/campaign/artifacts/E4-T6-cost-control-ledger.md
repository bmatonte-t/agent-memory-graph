# E4-T6 — Cost Control Ledger and Hard-Stop Workflow

**Epic:** E4 — Benchmark, Observability, and Cost Control Design
**Task:** E4-T6
**Date:** 2026-07-08
**Status:** Approved
**Owner:** Finance & Operations Lead

---

## 1. Budget and Financial Constraints

| Constraint | Value | Notes |
|-----------|-------|-------|
| **Total Campaign Budget** | USD 300 | Hard limit; no exceptions without Board approval |
| **Week 4 Spend Limit** | USD 80 | Cloud bootstrap + seed data + dry-run execution |
| **Week 5 Spend Limit** | USD 120 | Measured benchmark runs (360 runs) + adaptive exploration |
| **Week 6 Spend Limit** | USD 100 | Final validation + reporting + cleanup |
| **Cost Hard-Stop** | USD 260 | Execution halts when spend reaches this threshold |
| **Cost Soft-Stop** (Warning) | USD 250 | Alert triggered; PVL informed; escalation possible |
| **Cost Buffer (Reserve)** | USD 40 | For final cleanup and rundown operations |

---

## 2. Estimated Cost Breakdown

### 2.1 By Service

| Service | Week 4 | Week 5 | Week 6 | Total | Notes |
|---------|--------|--------|--------|-------|-------|
| **BigQuery** | $15 | $35 | $8 | $58 | 12 GB scanned; on-demand pricing |
| **Spanner** | $12 | $18 | $6 | $36 | Graph nodes + edges; ops/hour + storage |
| **Vertex AI (Flash)** | $25 | $55 | $20 | $100 | Primary agent inference; ~1,200–1,500 tokens/run |
| **Vertex AI (Pro)** | $8 | $12 | $4 | $24 | Secondary agents; heavier inference |
| **Cloud Run** | $3 | $4 | $2 | $9 | Backend execution; containerized tasks |
| **Cloud Scheduler** | $1 | $2 | $1 | $4 | Orchestration triggers |
| **Secret Manager** | $1 | $1 | $0 | $2 | Integration token storage (minimal) |
| **Cloud Logging** | $5 | $8 | $4 | $17 | Audit trails + observability logs |
| **Cloud Storage (GCS)** | $6 | $2 | $1 | $9 | Corpus + backup storage |
| **Network (egress)** | $2 | $3 | $2 | $7 | Cross-region egress; minimal |
| **Miscellaneous** | $2 | $0 | $0 | $2 | Unexpected overages buffer |
| **TOTAL** | **$80** | **$140** | **$48** | **$268** |

**Note:** Estimate includes 10% contingency. Actual cost may be $10–20 lower if:
- Fallback rate is <5% (fewer expensive Pro model calls)
- Graph queries cache efficiently (reduced Spanner ops)
- No API retry storms (retry backoff working)

---

### 2.2 Cost Per Run (Average)

**Assumptions:**
- 360 measured benchmark runs (12 scenarios × 30 runs)
- 50 warmup runs (dry-run, not counted toward KPIs)
- Average tokens per run: Flash model 1,400 (input 1,100 + output 300)

**Cost per Flash run:**
$$\text{Cost} = \frac{1100 \text{ tokens}}{1M} \times \$0.075 + \frac{300 \text{ tokens}}{1M} \times \$0.30 = \$0.000083 + \$0.000090 = \$0.000173$$

**Cost per Pro run (TA/CA agents):**
$$\text{Cost} = \frac{1100 \text{ tokens}}{1M} \times \$1.50 + \frac{300 \text{ tokens}}{1M} \times \$6.00 = \$0.00165 + \$0.00180 = \$0.00345$$

**Average across all agents (75% Flash, 25% Pro):**
$$\text{Avg} = 0.75 \times \$0.000173 + 0.25 \times \$0.00345 = \$0.00013 + \$0.00086 = \$0.00099 \approx \$0.001 \text{ per run}$$

**Total for 360 runs:** 360 × $0.001 = $0.36 (LLM inference alone)

**Including retrieval/BQ/storage overhead:** ~$1.50 per run (BQ queries + Spanner ops + storage)

**Expected Week 5 measured run cost:** 360 runs × $0.15/run = $54 (well within $120 budget for Week 5)

---

## 3. Cost Ledger Schema

### 3.1 Cost Ledger Table (BigQuery)

```sql
CREATE OR REPLACE TABLE `{{PROJECT_ID}}.benchmark_metrics.cost_ledger` (
  ledger_id STRING NOT NULL,
  campaign_id STRING NOT NULL,
  transaction_date DATE NOT NULL,
  transaction_hour TIMESTAMP NOT NULL,

  -- Allocation
  cost_category STRING NOT NULL,  -- enum: gcp_service, integration_token, contingency
  cost_subcategory STRING,  -- e.g., bigquery, vertex_ai_flash, vertex_ai_pro

  -- Amount
  amount_usd NUMERIC(7, 4) NOT NULL,
  currency STRING DEFAULT 'USD',

  -- Attribution
  run_id STRING,  -- if applicable (null for non-run costs like bootstrap)
  agent_id STRING,  -- if applicable
  scenario_id STRING,  -- if applicable

  -- Tracking
  gcp_billing_project_id STRING NOT NULL,
  gcp_sku_name STRING,  -- e.g., 'Analysis per GB'
  gcp_cost_details STRING,  -- JSON; raw billing detail

  -- Status
  status STRING NOT NULL,  -- enum: estimated, confirmed, reconciled
  reconciliation_timestamp_utc TIMESTAMP,

  -- Audit
  recorded_by STRING NOT NULL,
  recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),

  PRIMARY KEY (ledger_id),
  CONSTRAINT amount_positive CHECK (amount_usd > 0)
) PARTITION BY transaction_date
CLUSTER BY campaign_id, cost_category;
```

---

### 3.2 Cost Ledger Entry Types

| Entry Type | Category | Trigger | Typical Amount | Frequency |
|-----------|----------|---------|-----------------|-----------|
| Seed Data Load | gcp_service / bigquery | E5-T4: raw data loads to BigQuery | $8–15 | Once (Week 4) |
| Corpus Ingestion | gcp_service / cloud_storage | E5-T5: upload corpus to GCS | $2–4 | Once (Week 4) |
| Graph Seed | gcp_service / spanner | E5-T6: insert seed nodes/edges | $5–8 | Once (Week 4) |
| Dry-Run Execution | gcp_service / vertex_ai | E4-T7 & E5-T7: 10–20 warmup runs | $0.01–0.03 per run | Once (Week 4) |
| Benchmark Run | gcp_service / vertex_ai | E6: measured execution | $0.0009–0.0035 per run | 360 times (Week 5) |
| Retrieval Ops | gcp_service / spanner, bigquery | Every run: graph + BQ queries | $0.02–0.05 per run | 360 times (Week 5) |
| Logging & Audit | gcp_service / cloud_logging | E4-T4 audit/trace events | $0.02–0.03 per run | 360+ times (ongoing) |
| Integration Secrets | gcp_service / secret_manager | E2-T3: store + rotate tokens | $1–2 total | Once + rotation (Week 4) |
| API Calls | external / integration_api | E6 & E7: Slack, Calendar, GitHub, Jira | $0.001–0.01 per call | Variable |
| Cleanup & Teardown | gcp_service / various | E8-T2: delete campaign resources | $2–5 | Once (Week 6) |

---

## 4. Cost Tracking Workflow

### 4.1 Real-Time Cost Tracking

**Every 4 hours during Weeks 4–6:**

1. Query GCP Cloud Billing API for `{{CAMPAIGN_ID}}` labeled resources
2. Insert rows into `cost_ledger` table with status = 'estimated'
3. Compare cumulative cost against thresholds:
   - If cost < USD 250: continue normally (INFO log)
   - If USD 250 ≤ cost < USD 260: trigger soft-stop (WARN log + email PVL)
   - If cost ≥ USD 260: trigger hard-stop (ERROR log + halt execution)

**Query for Real-Time Spend:**

```sql
SELECT
  SUM(amount_usd) AS cumulative_cost_usd,
  MAX(transaction_hour) AS latest_update
FROM `{{PROJECT_ID}}.benchmark_metrics.cost_ledger`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND status IN ('estimated', 'confirmed')
  AND transaction_date >= CURRENT_DATE() - 7;
```

---

### 4.2 Daily Cost Reconciliation

**Every morning (06:00 UTC) during Weeks 4–6:**

1. Export GCP Cloud Billing data for `{{CAMPAIGN_ID}}` from previous day
2. Parse SKU costs by service (BigQuery, Spanner, Vertex AI, etc.)
3. Match to run_ids (if applicable) from `benchmark_metrics.runs` table
4. Insert reconciled entries into `cost_ledger` with status = 'reconciled'
5. Compare against forecast; flag significant variances (>10%)

**Cost Reconciliation Query:**

```sql
SELECT
  cost_category,
  SUM(amount_usd) AS daily_total_usd,
  COUNT(*) AS transaction_count,
  ROUND(AVG(amount_usd), 6) AS avg_amount_usd,
  ROUND(STDDEV(amount_usd), 6) AS stddev_amount_usd
FROM `{{PROJECT_ID}}.benchmark_metrics.cost_ledger`
WHERE campaign_id = '{{CAMPAIGN_ID}}'
  AND transaction_date = CURRENT_DATE() - 1
  AND status = 'reconciled'
GROUP BY cost_category
ORDER BY daily_total_usd DESC;
```

---

## 5. Hard-Stop Workflow

**Triggered when cumulative cost ≥ USD 260.**

### 5.1 Immediate Actions (T+0 minutes)

1. **Halt Benchmark Execution**
   - Cloud Scheduler stops sending new run tasks to Cloud Run
   - In-flight runs complete gracefully; no new runs accepted

2. **Alert PVL and Finance Lead**
   - Automated email with subject: "CAMPAIGN COST HARD-STOP: Spend at {{CURRENT_COST}}/{{BUDGET}}"
   - Include: current spend, weekly breakdown, remaining budget, recommendation

3. **Preserve State**
   - Flush all in-flight audit events to T3 (Spanner audit table)
   - Export current `benchmark_metrics.runs` snapshot to Cloud Storage (backup)

### 5.2 Assessment (T+30 minutes)

1. PVL and Finance Lead review cost report
2. Options:
   - **ACCEPT:** Stop campaign; proceed to E7 (analysis & synthesis) with available data
   - **REQUEST EXTENSION:** Increase budget with Board approval (rare; escalation required)
   - **OPTIMIZE & RESUME:** Reduce scope (e.g., skip Weeks 6 deep-dives) and resume

3. Record decision in issue/ticket with timestamp and approver

### 5.3 If RESUME Decision

1. Finance Lead approves revised budget and spend targets
2. Engineering Lead modifies Cloud Scheduler config to resume at reduced run rate
3. Log resume decision to `cost_ledger` with status='decision_resume' and approver_id
4. Resume benchmark execution with new cost limit (typically USD 260 + additional amount)

### 5.4 If STOP Decision

1. Log final decision to `cost_ledger` and campaign issue
2. Trigger cleanup sequence (E8-T2):
   - Delete benchmark resources (runs table data, Cloud Run tasks, etc.)
   - Export final metrics snapshot to Cloud Storage for archival
   - Preserve T3 audit table for compliance (immutable)
   - Release GCP resources (reserved capacity, disks, etc.)

---

## 6. Cost Forecasting and Burn Rate Analysis

### 6.1 Weekly Burn Rate Forecast

```sql
WITH daily_spend AS (
  SELECT
    EXTRACT(DATE FROM transaction_hour) AS spend_date,
    SUM(amount_usd) AS daily_amount_usd
  FROM `{{PROJECT_ID}}.benchmark_metrics.cost_ledger`
  WHERE campaign_id = '{{CAMPAIGN_ID}}'
    AND status IN ('confirmed', 'reconciled')
    AND transaction_date >= CURRENT_DATE() - 7
  GROUP BY spend_date
)
SELECT
  ROUND(AVG(daily_amount_usd), 2) AS avg_daily_burn_usd,
  ROUND(AVG(daily_amount_usd) * 7, 2) AS weekly_burn_forecast_usd,
  ROUND((SELECT SUM(amount_usd) FROM `{{PROJECT_ID}}.benchmark_metrics.cost_ledger`
    WHERE campaign_id = '{{CAMPAIGN_ID}}'
      AND status IN ('confirmed', 'reconciled')), 2) AS cumulative_spend_usd,
  ROUND(300 - (SELECT SUM(amount_usd) FROM `{{PROJECT_ID}}.benchmark_metrics.cost_ledger`
    WHERE campaign_id = '{{CAMPAIGN_ID}}'
      AND status IN ('confirmed', 'reconciled')), 2) AS remaining_budget_usd
FROM daily_spend;
```

**Output interpretation:**
- If avg_daily_burn > remaining_budget_usd / 7: on track to exceed USD 300 (raise alert)
- If avg_daily_burn < forecast: ahead of schedule; may reduce future days' allocations

---

## 7. Cost Ledger Reconciliation Audit

### 7.1 End-of-Campaign Cost Verification

**After Week 6 completion, run:**

```sql
WITH gcp_billing_total AS (
  SELECT SUM(amount_usd) AS billed_total_usd
  FROM `{{PROJECT_ID}}.benchmark_metrics.cost_ledger`
  WHERE campaign_id = '{{CAMPAIGN_ID}}'
    AND status = 'reconciled'
),
run_manifest_total AS (
  SELECT SUM(estimated_cost_usd) AS manifest_total_usd
  FROM `{{PROJECT_ID}}.benchmark_metrics.runs`
  WHERE campaign_id = '{{CAMPAIGN_ID}}'
)
SELECT
  billed_total_usd,
  manifest_total_usd,
  ROUND(ABS(billed_total_usd - manifest_total_usd), 4) AS variance_usd,
  ROUND(
    100 * ABS(billed_total_usd - manifest_total_usd) / GREATEST(billed_total_usd, 0.01),
    2
  ) AS variance_pct
FROM gcp_billing_total, run_manifest_total;
```

**Acceptable tolerance:** ≤ 2% variance (rounding, tax, unused reservations)
**Action if >2%:** Finance Lead investigates; files reconciliation note in campaign record

---

## 8. Cost Control Checklist (E4-T7 Dry-Run)

| Item | Status | Owner |
|------|--------|-------|
| ☐ Cost ledger table created and indexed | | Infrastructure Lead |
| ☐ GCP Cloud Billing export configured (daily) | | Finance Lead |
| ☐ Real-time cost query validated against actual GCP bill | | Finance Lead |
| ☐ Hard-stop automation test: halt at USD 260 trigger | | Infrastructure Lead |
| ☐ Cost reconciliation query spot-checked (last 3 days) | | Finance Lead |
| ☐ PVL email alert template approved | | PVL |
| ☐ Cleanup workflow documented and tested | | Infrastructure Lead |
| ☐ Budget variance <2% between forecast and actuals | | Finance Lead |

---

## 9. Cost Transparency Dashboard

**Recommended visualizations (Data Studio):**

1. **Budget Progress** — stacked bar: Week 4 / Week 5 / Week 6 spend vs. allocation
2. **Daily Burn Rate** — line chart: cumulative spend (X=date, Y=USD) with hard-stop marker at $260
3. **Cost by Service** — pie chart; breakdown: Vertex AI, BigQuery, Spanner, etc.
4. **Cost per Run** — scatter: X=run_id, Y=cost_usd; identify expensive outliers
5. **Forecast vs. Actual** — dual line chart; weekly forecast vs. actual cumulative
6. **Remaining Budget Countdown** — gauge; USD remaining vs. USD 260 hard-stop
7. **Cost Alert Threshold** — KPI: soft-stop ($250) and hard-stop ($260) highlighted in red

---

## 10. Financial Sign-Off

| Milestone | Date | Approver | Signature |
|-----------|------|----------|-----------|
| Budget approved (E1-T3) | 2026-06-29 | Finance Lead | ☐ |
| Week 4 forecast accepted | 2026-07-08 | PVL | ☐ |
| Week 5 forecast updated (post Week 4) | 2026-07-15 | PVL | ☐ |
| Hard-stop decision (if triggered) | TBD | PVL + Finance Lead | ☐ |
| Final cost reconciliation (Week 6 end) | 2026-07-27 | Finance Lead | ☐ |
