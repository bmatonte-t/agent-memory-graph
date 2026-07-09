# E3-T5 — Data Quality Scorecard Template

**Epic:** E3 — Data Design, Fixtures, and Provenance Preparation
**Task:** E3-T5
**Date:** 2026-07-08
**Status:** Approved
**Owner:** MLE Lead

---

## 1. DQ Gate Policy

Per campaign plan Section 7.5: **Benchmark execution is blocked until all mandatory DQ checks pass.**

A check PASSES if the measured value meets the threshold. A check FAILS if the threshold is violated. All FAIL results must be remediated before the Week 5 readiness gate (E6-T4).

---

## 2. Scorecard: BigQuery Structured Data

### Category R — Referential Integrity

| Check ID | Table | Constraint | Threshold | Query | Result Column |
|----------|-------|-----------|---------|-------|--------------|
| `DQ-R-01` | `order_items` | `order_id` must exist in `orders` | 0 orphans | See §3 | `orphan_order_items` |
| `DQ-R-02` | `order_items` | `product_id` must exist in `products` | 0 orphans | See §3 | `orphan_product_refs` |
| `DQ-R-03` | `orders` | `customer_id` must exist in `customers` | 0 orphans | See §3 | `orphan_orders` |
| `DQ-R-04` | `orders` | `account_id` must exist in `accounts` | 0 orphans | See §3 | `orphan_order_accounts` |
| `DQ-R-05` | `payments` | `order_id` must exist in `orders` | 0 orphans | See §3 | `orphan_payments` |
| `DQ-R-06` | `refunds` | `order_id` must exist in `orders` | 0 orphans | See §3 | `orphan_refund_orders` |
| `DQ-R-07` | `refunds` | `payment_id` must exist in `payments` | 0 orphans | See §3 | `orphan_refund_payments` |
| `DQ-R-08` | `support_tickets` | `customer_id` must exist in `customers` | 0 orphans | See §3 | `orphan_ticket_customers` |
| `DQ-R-09` | `support_tickets` | `order_id` (non-null) must exist in `orders` | 0 orphans | See §3 | `orphan_ticket_orders` |
| `DQ-R-10` | `marketing_interactions` | `customer_id` must exist in `customers` | 0 orphans | See §3 | `orphan_marketing` |
| `DQ-R-11` | `inventory_events` | `product_id` must exist in `products` | 0 orphans | See §3 | `orphan_inventory` |
| `DQ-R-12` | `task_queue_items` | `assigned_employee_id` (non-null) must exist in `employees` | 0 orphans | See §3 | `orphan_task_employees` |
| `DQ-R-13` | `employees` | `team_id` must exist in `teams` | 0 orphans | See §3 | `orphan_employees` |
| `DQ-R-14` | `customers` | `account_id` must exist in `accounts` | 0 orphans | See §3 | `orphan_customer_accounts` |

### Category N — Null Thresholds

| Check ID | Table | Column | Max Null % | Query | Result Column |
|----------|-------|--------|-----------|-------|--------------|
| `DQ-N-01` | `customers` | `customer_id` | 0% | See §3 | `null_pct_customer_id` |
| `DQ-N-02` | `customers` | `email` | 0% | See §3 | `null_pct_customer_email` |
| `DQ-N-03` | `orders` | `order_id` | 0% | See §3 | `null_pct_order_id` |
| `DQ-N-04` | `orders` | `customer_id` | 0% | See §3 | `null_pct_order_customer` |
| `DQ-N-05` | `orders` | `placed_at` | 0% | See §3 | `null_pct_order_placed_at` |
| `DQ-N-06` | `order_items` | `order_id` | 0% | See §3 | `null_pct_item_order_id` |
| `DQ-N-07` | `order_items` | `product_id` | 0% | See §3 | `null_pct_item_product_id` |
| `DQ-N-08` | `support_tickets` | `ticket_id` | 0% | See §3 | `null_pct_ticket_id` |
| `DQ-N-09` | `support_tickets` | `status` | 0% | See §3 | `null_pct_ticket_status` |
| `DQ-N-10` | `payments` | `payment_id` | 0% | See §3 | `null_pct_payment_id` |
| `DQ-N-11` | `payments` | `amount` | 0% | See §3 | `null_pct_payment_amount` |
| `DQ-N-12` | `products` | `sku` | 0% | See §3 | `null_pct_product_sku` |
| `DQ-N-13` | `employees` | `team_id` | ≤1% | See §3 | `null_pct_employee_team` |

### Category C — Cardinality

| Check ID | Metric | Expected Range | Query | Result Column |
|----------|--------|---------------|-------|--------------|
| `DQ-C-01` | Distinct `customer_id` in `customers` | 480,000–520,000 | See §3 | `distinct_customers` |
| `DQ-C-02` | Distinct `product_id` in `products` | 45,000–55,000 | See §3 | `distinct_products` |
| `DQ-C-03` | Avg `order_items` per `order` | 2.0–5.0 | See §3 | `avg_items_per_order` |
| `DQ-C-04` | `payments` per `order` | Exactly 1 per order | See §3 | `orders_without_payment` |
| `DQ-C-05` | `sla_config` rows | Exactly 4 | See §3 | `sla_config_count` |
| `DQ-C-06` | `teams` with at least 5 `employees` | 100% of teams | See §3 | `understaffed_teams_pct` |
| `DQ-C-07` | `refund` rate vs `order` count | 4–8% | See §3 | `refund_rate_pct` |

### Category D — Distribution Sanity

| Check ID | Metric | Expected Range | Query | Result Column |
|----------|--------|---------------|-------|--------------|
| `DQ-D-01` | Daily order count mean (weekday) | 1,000–6,000 orders/day | See §3 | `mean_daily_orders_weekday` |
| `DQ-D-02` | Daily order count CoV (coefficient of variation) | ≤1.5 (allows seasonality) | See §3 | `cov_daily_orders` |
| `DQ-D-03` | Daily new ticket count mean | 200–1,500 tickets/day | See §3 | `mean_daily_tickets` |
| `DQ-D-04` | `orders.status` distribution: delivered | ≥40% of total | See §3 | `pct_delivered_orders` |
| `DQ-D-05` | `support_tickets.priority` critical rate | 4–10% | See §3 | `pct_critical_tickets` |
| `DQ-D-06` | `marketing_interactions.event_type` unsubscribed rate | ≤5% | See §3 | `pct_unsubscribed_marketing` |
| `DQ-D-07` | `customers.consent_marketing = TRUE` rate | 80–90% | See §3 | `pct_marketing_consent` |

---

## 3. DQ Validation Queries

```sql
-- DQ-R-01: Orphan order_items (order_id not in orders)
SELECT COUNT(*) AS orphan_order_items
FROM `{{PROJECT_ID}}.curated_retail_campaign.order_items` oi
WHERE NOT EXISTS (
  SELECT 1 FROM `{{PROJECT_ID}}.curated_retail_campaign.orders` o
  WHERE o.order_id = oi.order_id
);

-- DQ-R-03: Orphan orders (customer_id not in customers)
SELECT COUNT(*) AS orphan_orders
FROM `{{PROJECT_ID}}.curated_retail_campaign.orders` o
WHERE NOT EXISTS (
  SELECT 1 FROM `{{PROJECT_ID}}.curated_retail_campaign.customers` c
  WHERE c.customer_id = o.customer_id
);

-- DQ-N-04: Null rate for orders.customer_id
SELECT ROUND(100.0 * COUNTIF(customer_id IS NULL) / COUNT(*), 4) AS null_pct_order_customer
FROM `{{PROJECT_ID}}.curated_retail_campaign.orders`;

-- DQ-C-03: Avg order_items per order
SELECT AVG(item_count) AS avg_items_per_order
FROM (
  SELECT order_id, COUNT(*) AS item_count
  FROM `{{PROJECT_ID}}.curated_retail_campaign.order_items`
  GROUP BY order_id
);

-- DQ-C-04: Orders without exactly one payment
SELECT COUNT(*) AS orders_without_payment
FROM `{{PROJECT_ID}}.curated_retail_campaign.orders` o
WHERE (
  SELECT COUNT(*) FROM `{{PROJECT_ID}}.curated_retail_campaign.payments` p
  WHERE p.order_id = o.order_id
) != 1;

-- DQ-D-01: Mean daily orders (weekday only)
SELECT AVG(daily_orders) AS mean_daily_orders_weekday
FROM (
  SELECT DATE(placed_at) AS order_date, COUNT(*) AS daily_orders
  FROM `{{PROJECT_ID}}.curated_retail_campaign.orders`
  WHERE EXTRACT(DAYOFWEEK FROM placed_at) NOT IN (1, 7)  -- exclude Sat/Sun
  GROUP BY order_date
);

-- DQ-D-04: Percent of orders with status = 'delivered'
SELECT ROUND(100.0 * COUNTIF(status = 'delivered') / COUNT(*), 2) AS pct_delivered_orders
FROM `{{PROJECT_ID}}.curated_retail_campaign.orders`;
```

*All remaining DQ queries follow the same pattern; implement in `scripts/run_dq_checks.py` at E6-T4.*

---

## 4. Scorecard: Spanner Graph Connectivity

| Check ID | Metric | Threshold | Notes |
|----------|--------|---------|-------|
| `DQ-G-01` | `Customer` nodes with no `CUSTOMER_PLACED_ORDER` edge | ≤5% of Customer count | Isolated customer threshold |
| `DQ-G-02` | `Order` nodes with no `ORDER_CONTAINS_PRODUCT` edge | 0 | Every order must have at least one item |
| `DQ-G-03` | `Agent` nodes with no `AGENT_MEMBER_OF_TEAM` edge | 0 | All agents must belong to a team |
| `DQ-G-04` | `Team` nodes with no `AGENT_MEMBER_OF_TEAM` edges | 0 | No empty teams |
| `DQ-G-05` | `Ticket` nodes with no `CUSTOMER_OPENED_TICKET` edge | 0 | Every ticket has a customer |
| `DQ-G-06` | `Product` nodes with no edges of any type | ≤5% of Product count | Isolated product threshold |
| `DQ-G-07` | No-evidence fixture `NE-001` customer present in graph | Must return 0 rows | Validates NE fixture absence |
| `DQ-G-08` | No-evidence fixture `NE-002` product present in graph | Must return 0 rows | Validates NE fixture absence |
| `DQ-G-09` | All nodes have `cognitive_weight >= 0.30` | 100% | Ensures traversal visibility post-seed |

### Graph DQ Validation Queries

```sql
-- DQ-G-01: Isolated customers (no orders)
SELECT ROUND(100.0 * isolated_count / total_count, 2) AS isolated_customer_pct
FROM (
  SELECT
    (SELECT COUNT(*) FROM CustomerNodes c
     WHERE NOT EXISTS (
       SELECT 1 FROM GRAPH_TABLE(MemoryGraph
         MATCH (cx:Customer {customer_id: c.customer_id})-[:CUSTOMER_PLACED_ORDER]->(o:Order)
         RETURN 1)
     )) AS isolated_count,
    (SELECT COUNT(*) FROM CustomerNodes) AS total_count
);

-- DQ-G-07: No-evidence fixture presence check
SELECT COUNT(*) AS ne001_present FROM CustomerNodes
WHERE customer_id = '00000000-0000-0000-0000-000000000001';
-- Must be 0

-- DQ-G-09: Nodes below cognitive horizon
SELECT COUNT(*) AS below_horizon
FROM (
  SELECT cognitive_weight FROM CustomerNodes
  UNION ALL SELECT cognitive_weight FROM OrderNodes
  UNION ALL SELECT cognitive_weight FROM TicketNodes
  UNION ALL SELECT cognitive_weight FROM ProductNodes
  UNION ALL SELECT cognitive_weight FROM AgentNodes
)
WHERE cognitive_weight < 0.30;
-- Must be 0
```

---

## 5. Scorecard: GCS Corpus Completeness

| Check ID | Metric | Threshold |
|----------|--------|---------|
| `DQ-GCS-01` | CORP-01 object count in GCS prefix `product-manuals/` | 480–520 |
| `DQ-GCS-02` | CORP-02 object count in GCS prefix `policy-docs/` | 38–42 |
| `DQ-GCS-03` | CORP-03 object count in GCS prefix `sop-documents/` | 57–63 |
| `DQ-GCS-04` | CORP-04 object count in GCS prefix `customer-comms/` | 1,150–1,250 |
| `DQ-GCS-05` | CORP-05 object count in GCS prefix `integration-event-narratives/` | 475–525 |
| `DQ-GCS-06` | All objects have mandatory metadata tags | 100% compliant |

---

## 6. Scorecard Result Sheet (Filled at E6-T4)

| Check ID | Measured Value | Threshold | Pass/Fail | Run Date | Notes |
|----------|---------------|---------|---------|---------|-------|
| DQ-R-01 through DQ-R-14 | — | 0 orphans | — | — | — |
| DQ-N-01 through DQ-N-13 | — | ≤0% or ≤1% | — | — | — |
| DQ-C-01 through DQ-C-07 | — | Per range | — | — | — |
| DQ-D-01 through DQ-D-07 | — | Per range | — | — | — |
| DQ-G-01 through DQ-G-09 | — | Per threshold | — | — | — |
| DQ-GCS-01 through DQ-GCS-06 | — | Per count | — | — | — |

**Overall DQ Gate:** [ ] PASS — [ ] FAIL (requires remediation before benchmark)

---

## 7. Remediation Protocol

If any mandatory DQ check fails at E6-T4:
1. ML Lead documents the failure with root cause analysis.
2. PE executes targeted re-ingestion or transformation fix.
3. ML Lead re-runs affected DQ checks only.
4. Results are updated in the scorecard result sheet.
5. PVL approves remediation completion before E6-T7 freeze.
