# E6-T4 — Data Quality Validation and Gate Execution

**Epic:** E6 — Cloud Data Provisioning and Integration Bring-up
**Task:** E6-T4
**Date:** 2026-07-19
**Status:** Approved
**Owner:** Data Lead

---

## 1. Objective

Execute frozen data quality scorecard (E3-T5: 37 checks) on provisioned BigQuery datasets, Spanner graph, and corpus. Document 0-violation expectation and produce DQ validation report.

**Dependencies:** E3-T5 (DQ scorecard), E6-T1 (BQ datasets), E6-T2 (corpus), E6-T3 (Spanner graph)

---

## 2. DQ Scorecard (37 Checks, Frozen from E3-T5)

### 2.1 Data Completeness Checks (8 checks)

| Check ID | Table | Column | Expected | Actual | Status |
|----------|-------|--------|----------|--------|--------|
| **DQ-C01** | raw_olist_orders | order_id | 0 NULLs | — | ☐ |
| **DQ-C02** | raw_olist_orders | customer_id | 0 NULLs | — | ☐ |
| **DQ-C03** | curated_retail_campaign.customers | email | >90% populated | — | ☐ |
| **DQ-C04** | curated_retail_campaign.products | sku | 0 NULLs | — | ☐ |
| **DQ-C05** | curated_retail_campaign.orders | total_amount | 0 NULLs | — | ☐ |
| **DQ-C06** | memory_nodes | node_id | 0 NULLs | — | ☐ |
| **DQ-C07** | memory_edges | source_node_id | 0 NULLs | — | ☐ |
| **DQ-C08** | corpus_index | doc_id | 2,400 rows | — | ☐ |

### 2.2 Data Uniqueness Checks (6 checks)

| Check ID | Table | Column | Constraint | Expected | Status |
|----------|-------|--------|-----------|----------|--------|
| **DQ-U01** | raw_olist_customers | customer_id | Primary Key | 0 duplicates | ☐ |
| **DQ-U02** | curated_retail_campaign.customers | customer_id | Unique | 0 duplicates | ☐ |
| **DQ-U03** | curated_retail_campaign.products | sku | Unique | 0 duplicates | ☐ |
| **DQ-U04** | memory_nodes | (tenant_id, node_id) | Composite PK | 0 duplicates | ☐ |
| **DQ-U05** | memory_edges | (tenant_id, edge_id) | Composite PK | 0 duplicates | ☐ |
| **DQ-U06** | corpus_index | doc_id | Unique | 0 duplicates | ☐ |

### 2.3 Data Validity Checks (8 checks)

| Check ID | Table | Column | Validation | Expected | Status |
|----------|-------|--------|-----------|----------|--------|
| **DQ-V01** | curated_retail_campaign.customers | created_at | ISO 8601 date | 100% valid | ☐ |
| **DQ-V02** | curated_retail_campaign.orders | total_amount | NUMERIC > 0 | 100% > 0 | ☐ |
| **DQ-V03** | curated_retail_campaign.orders | status | ENUM in [pending, confirmed, shipped, delivered, cancelled] | 100% valid | ☐ |
| **DQ-V04** | memory_nodes | cognitive_weight | NUMERIC 0.0–1.0 | 100% in range | ☐ |
| **DQ-V05** | memory_edges | cognitive_weight | NUMERIC 0.0–1.0 | 100% in range | ☐ |
| **DQ-V06** | corpus_index | format | ENUM in [markdown, html, json, pdf, csv, plaintext] | 100% valid | ☐ |
| **DQ-V07** | raw_retail_public.* | date columns | ISO 8601 | 100% valid | ☐ |
| **DQ-V08** | curated_retail_campaign.* | email columns | RFC 5322 format | >95% valid | ☐ |

### 2.4 Data Consistency Checks (10 checks)

| Check ID | Assertion | Query | Expected | Status |
|----------|-----------|-------|----------|--------|
| **DQ-X01** | FK: orders.customer_id → customers.customer_id | Left-join orphan check | 0 orphans | ☐ |
| **DQ-X02** | FK: order_items.order_id → orders.order_id | Left-join orphan check | 0 orphans | ☐ |
| **DQ-X03** | FK: memory_edges.source_node_id → memory_nodes.node_id | Left-join orphan check | 0 orphans | ☐ |
| **DQ-X04** | Fact table grains: orders (1 row per order) | COUNT=COUNT(DISTINCT order_id) | 100% match | ☐ |
| **DQ-X05** | Referential consistency: payments per order ≤ order_items count | Audit check | 100% consistent | ☐ |
| **DQ-X06** | Graph connectivity: CUSTOMER_PLACED_ORDER edge count ≤ curated orders count | Compare counts | ≤ expected | ☐ |
| **DQ-X07** | Data freshness: curated tables populated from raw | Check updated_at > raw load time | 100% fresh | ☐ |
| **DQ-X08** | Memory tier isolation: T1 nodes have session_id | Check presence | >80% have session | ☐ |
| **DQ-X09** | Corpus document dedup: no duplicate doc_id | Check uniqueness | 0 duplicates | ☐ |
| **DQ-X10** | Audit immutability: T3 nodes have no update timestamps | Check created_at only | 100% no updates | ☐ |

### 2.5 Data Accuracy Checks (5 checks)

| Check ID | Table | Validation | Tolerance | Status |
|----------|-------|-----------|-----------|--------|
| **DQ-A01** | curated_retail_campaign.orders | SUM(total_amount) vs. raw orders | ≤1% variance | ☐ |
| **DQ-A02** | curated_retail_campaign.customers | De-duped count vs. raw unique | ≤2% variance | ☐ |
| **DQ-A03** | memory_nodes | 239 seed nodes + audit operations | Expected count ±5% | ☐ |
| **DQ-A04** | corpus_index | 2,400 corpus documents indexed | Expected count ±1% | ☐ |
| **DQ-A05** | Cost ledger reconciliation | Sum(cost_ledger) vs. GCP billing API | ≤2% variance | ☐ |

---

## 3. DQ Validation Queries

### 3.1 Completeness Queries

```sql
-- DQ-C01: raw_olist_orders.order_id should have no NULLs
SELECT COUNT(*) AS null_count
FROM `{{PROJECT_ID}}.raw_retail_public.raw_olist_orders`
WHERE order_id IS NULL;
-- Expected: 0

-- DQ-C03: customers.email >90% populated
SELECT
  ROUND(COUNT(CASE WHEN email IS NOT NULL THEN 1 END)
    / COUNT(*) * 100, 2) AS email_populated_pct
FROM `{{PROJECT_ID}}.curated_retail_campaign.customers`;
-- Expected: >90%

-- DQ-C08: corpus_index has 2,400 rows
SELECT COUNT(*) AS corpus_doc_count
FROM `{{PROJECT_ID}}.benchmark_metrics.corpus_index`;
-- Expected: 2,400
```

### 3.2 Uniqueness Queries

```sql
-- DQ-U02: customers.customer_id unique
SELECT
  customer_id,
  COUNT(*) AS dup_count
FROM `{{PROJECT_ID}}.curated_retail_campaign.customers`
GROUP BY customer_id
HAVING COUNT(*) > 1;
-- Expected: 0 rows (no duplicates)

-- DQ-U04: memory_nodes composite PK (tenant_id, node_id) unique
SELECT
  tenant_id,
  node_id,
  COUNT(*) AS dup_count
FROM `{{PROJECT_ID}}.{{SPANNER_INSTANCE}}.memory_nodes`
GROUP BY tenant_id, node_id
HAVING COUNT(*) > 1;
-- Expected: 0 rows (no duplicates)
```

### 3.3 Validity Queries

```sql
-- DQ-V02: orders.total_amount > 0
SELECT COUNT(*) AS invalid_amounts
FROM `{{PROJECT_ID}}.curated_retail_campaign.orders`
WHERE total_amount IS NULL OR total_amount <= 0;
-- Expected: 0

-- DQ-V04: memory_nodes.cognitive_weight in [0.0, 1.0]
SELECT
  COUNT(*) AS out_of_range,
  MIN(cognitive_weight) AS min_weight,
  MAX(cognitive_weight) AS max_weight
FROM `{{PROJECT_ID}}.{{SPANNER_INSTANCE}}.memory_nodes`
WHERE cognitive_weight < 0.0 OR cognitive_weight > 1.0;
-- Expected: out_of_range=0, min≥0.0, max≤1.0

-- DQ-V08: email format validation (RFC 5322 basic check)
SELECT COUNT(*) AS invalid_emails
FROM `{{PROJECT_ID}}.curated_retail_campaign.customers`
WHERE email IS NOT NULL
  AND (NOT REGEXP_CONTAINS(email, r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'));
-- Expected: <5% of total emails
```

### 3.4 Consistency Queries

```sql
-- DQ-X01: FK check - orders.customer_id → customers.customer_id
SELECT COUNT(*) AS orphan_orders
FROM `{{PROJECT_ID}}.curated_retail_campaign.orders` o
LEFT JOIN `{{PROJECT_ID}}.curated_retail_campaign.customers` c
  ON o.customer_id = c.customer_id
WHERE c.customer_id IS NULL;
-- Expected: 0

-- DQ-X04: Fact table grain - orders (1 row per order)
SELECT
  COUNT(*) AS total_rows,
  COUNT(DISTINCT order_id) AS distinct_orders,
  CASE WHEN COUNT(*) = COUNT(DISTINCT order_id) THEN 'PASS' ELSE 'FAIL' END AS grain_check
FROM `{{PROJECT_ID}}.curated_retail_campaign.orders`;
-- Expected: total_rows = distinct_orders (grain is valid)

-- DQ-X06: Graph connectivity - CUSTOMER_PLACED_ORDER edge count
SELECT
  (SELECT COUNT(*) FROM `{{PROJECT_ID}}.{{SPANNER_INSTANCE}}.memory_edges`
   WHERE tenant_id = '{{TENANT_ID}}' AND label = 'CUSTOMER_PLACED_ORDER') AS edge_count,
  (SELECT COUNT(*) FROM `{{PROJECT_ID}}.curated_retail_campaign.orders`) AS order_count,
  CASE WHEN edge_count <= order_count THEN 'PASS' ELSE 'FAIL' END AS connectivity_check;
-- Expected: edge_count ≤ order_count
```

### 3.5 Accuracy Queries

```sql
-- DQ-A01: orders aggregate reconciliation
SELECT
  ROUND(
    ABS(
      (SELECT SUM(total_amount) FROM `{{PROJECT_ID}}.curated_retail_campaign.orders`)
      -
      (SELECT SUM(CAST(price AS NUMERIC)) FROM `{{PROJECT_ID}}.raw_retail_public.raw_olist_orders`)
    ) / NULLIF(SELECT SUM(CAST(price AS NUMERIC)) FROM `{{PROJECT_ID}}.raw_retail_public.raw_olist_orders`, 0) * 100,
    2
  ) AS variance_pct;
-- Expected: ≤1%

-- DQ-A03: Spanner node count validation
SELECT
  COUNT(*) AS actual_count,
  ABS(COUNT(*) - 239) / 239.0 * 100 AS variance_pct
FROM `{{PROJECT_ID}}.{{SPANNER_INSTANCE}}.memory_nodes`
WHERE tenant_id = '{{TENANT_ID}}';
-- Expected: ≈239 (±5% = 228–251)

-- DQ-A04: Corpus index count
SELECT
  COUNT(*) AS corpus_docs,
  ABS(COUNT(*) - 2400) / 2400.0 * 100 AS variance_pct
FROM `{{PROJECT_ID}}.benchmark_metrics.corpus_index`;
-- Expected: 2,400 (±1% = 2,376–2,424)
```

---

## 4. DQ Validation Report

### 4.1 Report Template (markdown)

```markdown
# E6 Data Quality Validation Report
**Date:** 2026-07-19
**Campaign:** amg-validation-2026-q3
**Status:** PASS / FAIL

## Executive Summary
- **Total Checks:** 37
- **Passed:** {{PASSED_COUNT}} ✓
- **Failed:** {{FAILED_COUNT}} ✗
- **Pass Rate:** {{PASS_PCT}}%

## By Category

### Completeness (8 checks)
| Check | Status | Details |
|-------|--------|---------|
| DQ-C01 | ✓ PASS | order_id: 0 NULLs (expected 0) |
| ... | ... | ... |

### Uniqueness (6 checks)
| Check | Status | Details |
|-------|--------|---------|
| DQ-U01 | ✓ PASS | customer_id: 0 duplicates |
| ... | ... | ... |

### Validity (8 checks)
| Check | Status | Details |
|-------|--------|---------|
| DQ-V01 | ✓ PASS | created_at: 100% ISO 8601 |
| ... | ... | ... |

### Consistency (10 checks)
| Check | Status | Details |
|-------|--------|---------|
| DQ-X01 | ✓ PASS | FK orphans: 0 |
| ... | ... | ... |

### Accuracy (5 checks)
| Check | Status | Details |
|-------|--------|---------|
| DQ-A01 | ✓ PASS | orders sum variance: 0.3% |
| ... | ... | ... |

## Issue Summary
- **CRITICAL:** 0
- **HIGH:** 0
- **MEDIUM:** 0
- **LOW:** 0

## Sign-Off
- Data Lead: ☐
- Infrastructure Lead: ☐
- Program Manager: ☐

**Approval Status:** ☐ APPROVED (all 37 checks pass)
```

---

## 5. Validation Execution Plan

### 5.1 Day 1: BigQuery DQ Execution

```
09:00 — Run all 22 BQ-specific checks (C01–C08, U01–U06, V01–V04, V07–V08, X01–X07, A01–A02)
11:00 — Aggregate results into validation report
12:00 — Address any failures (expected: 0)
14:00 — CHECKPOINT: BigQuery DQ passed (22/22 checks)
```

### 5.2 Day 2: Spanner Graph DQ Execution

```
09:00 — Run Spanner-specific checks (C06–C07, U04–U05, V04–V05, X08–X10, A03)
10:00 — Verify graph topology (239 nodes, ~508 edges)
11:00 — Validate tier separation (T1/T2/T3)
12:00 — CHECKPOINT: Spanner DQ passed (10/10 checks)
```

### 5.3 Day 3: Corpus & Cross-Domain DQ Execution

```
09:00 — Run corpus checks (C08, U06, V06, X09, A04)
10:00 — Execute cost reconciliation (A05: cost_ledger vs. billing API)
11:00 — Aggregate all 37 check results
12:00 — Generate final DQ validation report
14:00 — CHECKPOINT: All DQ passed (37/37 checks); GATE CONDITION MET
```

---

## 6. Failure Response Workflow

**If any check fails:**

```
1. Identify root cause (data, schema, configuration)
2. Log issue in gates/E6-issues.md with:
   - Check ID and expected vs. actual
   - Impact severity (Critical/High/Medium/Low)
   - Proposed remediation
3. Execute fix:
   - Data fix: UPDATE/DELETE query with audit log
   - Schema fix: ALTER TABLE or migration
   - Config fix: Adjust parameters
4. Re-run check to verify fix
5. Document resolution in E6-issues.md
```

**Expected outcome:** 0 failures (frozen data from E3-T1, E3-T4 designs)

---

## 7. Quality Checklist

| Check | Status | Expected |
|-------|--------|----------|
| All 37 DQ checks defined and ready | ☐ | ✓ Complete |
| BigQuery queries validated (syntax) | ☐ | ✓ All queries pass dry-run |
| Spanner queries validated | ☐ | ✓ All queries pass test execution |
| Pass thresholds set appropriately | ☐ | ✓ Tolerance documented |
| Validation report template ready | ☐ | ✓ Markdown template prepared |

---

## 8. Cost Estimate (E6-T4)

| Resource | Quantity | Unit Cost | Total |
|----------|----------|-----------|-------|
| BigQuery Validation Queries | ~25 GB scanned | $7.50/TB | $0.19 |
| Spanner Validation Queries | ~50 ops | $0.01/million | $0.0001 |
| Report Generation | 1 report | Negligible | $0.00 |
| **Total (E6-T4)** | — | — | **~$0.19** |

**Budget Impact:** Week 5 DQ budget: $3 (includes T4 complete); $0.19 utilization

---

## 9. Sign-Off

| Role | Owner | Sign-Off | Date |
|------|-------|----------|------|
| Data Lead | J. Patel | ☐ | ____ |
| Infrastructure Lead | T. Chen | ☐ | ____ |
| Program Manager | S. Gupta | ☐ | ____ |
