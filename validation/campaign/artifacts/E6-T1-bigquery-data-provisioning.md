# E6-T1 — BigQuery Data Provisioning and Ingestion

**Epic:** E6 — Cloud Data Provisioning and Integration Bring-up
**Task:** E6-T1
**Date:** 2026-07-16
**Status:** Approved
**Owner:** Data Lead

---

## 1. Objective

Provision and populate BigQuery datasets with structured data from frozen sources (E3-T2: DS-01–DS-06). Load raw and curated data layers with full lineage tracking and metadata governance.

**Dependencies:** E3-T2 (source inventory), E3-T1 (schema), E5-T8 (BigQuery datasets created)

---

## 2. Data Source Inventory (Frozen from E3-T2)

| Source ID | Name | Volume | Format | License | Raw Table | Status |
|-----------|------|--------|--------|---------|-----------|--------|
| **DS-01** | Olist Public Dataset | 120 MB | CSV | CC0 (Public) | raw_olist_* (7 tables) | ☐ Load |
| **DS-02** | UCI ML Repository | 43 MB | CSV | CC0 | raw_uci_* (3 tables) | ☐ Load |
| **DS-03** | Synthetic Retail (Customers) | 28 MB | JSON | Internal | raw_customers_synthetic | ☐ Generate |
| **DS-04** | Synthetic Retail (Orders) | 34 MB | JSON | Internal | raw_orders_synthetic | ☐ Generate |
| **DS-05** | Synthetic Retail (Events) | 18 MB | JSON | Internal | raw_events_synthetic | ☐ Generate |
| **DS-06** | Synthetic Support Data | 12 MB | JSON | Internal | raw_support_synthetic | ☐ Generate |
| **Total** | — | ~255 MB | Mixed | — | 14 raw tables | — |

---

## 3. BigQuery Dataset Architecture

### 3.1 Three-Tier Data Structure

```
benchmark_metrics
├── raw_retail_public (raw data layer; immutable after load)
│   ├── raw_olist_orders
│   ├── raw_olist_customers
│   ├── raw_olist_order_items
│   ├── raw_olist_payments
│   ├── raw_olist_reviews
│   ├── raw_uci_sales_records
│   ├── raw_customers_synthetic
│   ├── raw_orders_synthetic
│   ├── raw_events_synthetic
│   ├── raw_support_synthetic
│   └── metadata_source_lineage (provenance table)
│
├── curated_retail_campaign (curated business entities)
│   ├── customers (deduped, validated)
│   ├── products (enriched, categorized)
│   ├── accounts (customer aggregations)
│   ├── orders (fact table with foreign keys)
│   ├── order_items (order line items)
│   ├── payments (payment method mappings)
│   ├── refunds (return transactions)
│   ├── inventory_events (stock level changes)
│   ├── support_tickets (customer service data)
│   ├── sla_config (service level agreements)
│   ├── marketing_interactions (campaigns)
│   ├── employees (workforce data)
│   ├── teams (organizational units)
│   └── task_queue_items (job queue)
│
└── benchmark_metrics (observability & KPIs)
    ├── runs (360+ benchmark runs)
    ├── cost_ledger (cost tracking)
    └── agent_analytics (performance metrics)
```

### 3.2 Schema Mapping (Frozen from E3-T1)

**14 curated tables with complete schema:**

| Table | Rows | Key Columns | Grain |
|-------|------|------------|-------|
| customers | ~500 | customer_id, email, name, created_at | One row per unique customer |
| products | ~300 | product_id, category, price, sku | One row per product |
| accounts | ~150 | account_id, customer_id, type | One row per account |
| orders | ~5,000 | order_id, customer_id, order_date, total_amount | One row per order |
| order_items | ~12,000 | order_item_id, order_id, product_id, quantity, price | One row per line item |
| payments | ~5,000 | payment_id, order_id, method, amount, status | One row per payment |
| refunds | ~800 | refund_id, order_id, reason, amount, date | One row per refund |
| inventory_events | ~3,500 | event_id, product_id, warehouse_id, quantity_change | One row per stock change |
| support_tickets | ~1,200 | ticket_id, customer_id, subject, created_date, resolved_date | One row per support case |
| sla_config | 5 | sla_id, priority_level, response_hours, resolution_hours | One row per SLA tier |
| marketing_interactions | ~2,000 | interaction_id, customer_id, campaign_id, channel, timestamp | One row per interaction |
| employees | ~50 | employee_id, name, department, hire_date | One row per employee |
| teams | ~10 | team_id, name, manager_id, department | One row per team |
| task_queue_items | ~400 | task_id, assigned_to, priority, status, created_at | One row per queued task |

---

## 4. Data Loading Pipeline

### 4.1 Raw Data Ingestion (Olist + UCI)

**Source:** Public dataset URLs downloaded to GCS

```bash
# Step 1: Download public datasets to GCS
gsutil cp gs://public-datasets/olist/* gs://amg-campaign-corpus-q3/sources/olist/
gsutil cp gs://public-datasets/uci/* gs://amg-campaign-corpus-q3/sources/uci/

# Step 2: Load CSV files into BigQuery raw tables
bq load \
  --source_format=CSV \
  --skip_leading_rows=1 \
  --allow_quoted_newlines=true \
  {{PROJECT_ID}}:raw_retail_public.raw_olist_orders \
  gs://amg-campaign-corpus-q3/sources/olist/orders.csv \
  order_id:INTEGER,customer_id:STRING,order_date:TIMESTAMP,order_status:STRING

# (Similar commands for remaining Olist and UCI tables)
```

### 4.2 Synthetic Data Generation (DS-03–DS-06)

**Source:** Python scripts with seed-based randomization

```python
# generate_synthetic_data.py
import pandas as pd
import random
from datetime import datetime, timedelta

SEED = 42  # Frozen seed for reproducibility
random.seed(SEED)

def generate_customers(count=500):
    """Generate synthetic customer records."""
    customers = []
    for i in range(count):
        customers.append({
            'customer_id': f'CUST-{i:06d}',
            'email': f'customer{i}@example.com',
            'name': f'Customer {i}',
            'created_at': datetime(2024, 1, 1) + timedelta(days=random.randint(0, 365)),
            'country': random.choice(['US', 'BR', 'MX', 'CA']),
            'lifetime_value': round(random.uniform(50, 5000), 2)
        })
    return pd.DataFrame(customers)

def generate_orders(customer_count=500, orders_per_customer=10):
    """Generate synthetic order records."""
    orders = []
    for c in range(customer_count):
        for o in range(orders_per_customer):
            orders.append({
                'order_id': f'ORD-{c:06d}-{o:04d}',
                'customer_id': f'CUST-{c:06d}',
                'order_date': datetime(2024, 1, 1) + timedelta(days=random.randint(0, 365)),
                'total_amount': round(random.uniform(10, 500), 2),
                'status': random.choice(['pending', 'confirmed', 'shipped', 'delivered', 'cancelled'])
            })
    return pd.DataFrame(orders)

# Generate all synthetic tables
df_customers = generate_customers(500)
df_orders = generate_orders(500, 10)
df_events = generate_events(5000)
df_support = generate_support_tickets(1200)

# Save to CSV for BigQuery loading
df_customers.to_csv('/tmp/customers_synthetic.csv', index=False)
df_orders.to_csv('/tmp/orders_synthetic.csv', index=False)
df_events.to_csv('/tmp/events_synthetic.csv', index=False)
df_support.to_csv('/tmp/support_synthetic.csv', index=False)
```

**Upload to GCS and load:**
```bash
gsutil cp /tmp/*_synthetic.csv gs://amg-campaign-corpus-q3/sources/synthetic/

bq load \
  --source_format=CSV \
  --skip_leading_rows=1 \
  {{PROJECT_ID}}:raw_retail_public.raw_customers_synthetic \
  gs://amg-campaign-corpus-q3/sources/synthetic/customers_synthetic.csv
```

### 4.3 Data Transformation (Raw → Curated)

**Transformation logic (Dataform or dbt):**

```sql
-- Transform raw_olist_* and raw_uci_* into curated schema
-- Example: Create curated.customers from raw sources

CREATE OR REPLACE TABLE `{{PROJECT_ID}}.curated_retail_campaign.customers` AS
SELECT
  DISTINCT
  COALESCE(ro.customer_id, ru.cust_id, rs.customer_id) AS customer_id,
  COALESCE(ro.customer_email, ru.email, rs.email) AS email,
  COALESCE(ro.customer_unique_id, ru.cust_name, rs.name) AS name,
  MIN(COALESCE(ro.order_purchase_timestamp, ru.order_date, rs.created_at))
    AS created_at,
  COALESCE(ro.customer_state, ru.region, rs.state) AS state,
  COUNT(DISTINCT COALESCE(ro.order_id, ru.order_id, rs.ticket_id)) AS total_interactions,
  SUM(COALESCE(ro.price, ru.amount, 0)) AS lifetime_value
FROM
  `{{PROJECT_ID}}.raw_retail_public.raw_olist_customers` ro
FULL OUTER JOIN `{{PROJECT_ID}}.raw_retail_public.raw_uci_sales_records` ru
  ON ro.customer_id = ru.cust_id
FULL OUTER JOIN `{{PROJECT_ID}}.raw_retail_public.raw_customers_synthetic` rs
  ON ro.customer_id = rs.customer_id
WHERE
  customer_id IS NOT NULL
GROUP BY
  customer_id, email, name, state;
```

---

## 5. Data Loading Execution Plan

### 5.1 Day 1: Public Data (Olist + UCI)

```
09:00 — Download public datasets to GCS
10:00 — Validate CSV structure and row counts
11:00 — Load raw_olist_* tables (7 tables, ~148 MB)
13:00 — Load raw_uci_* tables (3 tables, ~43 MB)
14:00 — Verify row counts and data quality
16:00 — CHECKPOINT: Raw public data loaded successfully
```

**Verification queries:**
```sql
-- Check raw Olist tables
SELECT table_name, row_count FROM `{{PROJECT_ID}}.raw_retail_public.__TABLES__`
WHERE table_name LIKE 'raw_olist_%';

-- Expected: 7 tables, ~148 MB total
SELECT SUM(size_bytes) / (1024*1024) AS size_mb
FROM `{{PROJECT_ID}}.raw_retail_public.__TABLES__`
WHERE table_name LIKE 'raw_olist_%';
```

### 5.2 Day 2: Synthetic Data (DS-03–DS-06)

```
09:00 — Run data generation scripts (Python)
10:00 — Validate generated CSV files (row counts, schema)
11:00 — Upload to GCS (amg-campaign-corpus-q3/sources/synthetic/)
12:00 — Load raw_customers_synthetic, raw_orders_synthetic, raw_events_synthetic, raw_support_synthetic
14:00 — Verify row counts (500 customers, 5,000 orders, 3,500 events, 1,200 tickets)
16:00 — CHECKPOINT: All raw synthetic data loaded
```

**Seed reproducibility check:**
```python
# Verify same seed produces same data
df1 = generate_customers(500)  # Run 1
df2 = generate_customers(500)  # Run 2
assert df1.equals(df2)  # Must be identical
```

### 5.3 Day 3: Transformation (Raw → Curated)

```
09:00 — Apply transformation SQL (14 curated tables)
10:00 — Verify lineage (raw → curated mapping)
12:00 — Validate foreign key relationships
14:00 — Spot-check sample rows across all tables
16:00 — CHECKPOINT: Curated layer populated and validated
```

**Expected row counts (curated layer):**
```sql
-- Verify curated table population
SELECT
  table_name,
  row_count,
  ROUND(size_bytes / (1024*1024), 2) AS size_mb
FROM `{{PROJECT_ID}}.curated_retail_campaign.__TABLES__`
ORDER BY table_name;

-- Expected: 14 tables, ~25 GB total
```

---

## 6. Metadata and Lineage Tracking

### 6.1 Lineage Table (raw_retail_public.metadata_source_lineage)

```sql
CREATE TABLE `{{PROJECT_ID}}.raw_retail_public.metadata_source_lineage` (
  source_id STRING NOT NULL,
  source_name STRING,
  raw_table_name STRING,
  curated_table_names ARRAY<STRING>,
  volume_bytes INT64,
  row_count INT64,
  license_type STRING,
  load_timestamp TIMESTAMP,
  data_freshness STRING,
  lineage_json STRING  -- JSON doc with transformation mapping
);

-- Insert lineage records
INSERT INTO `{{PROJECT_ID}}.raw_retail_public.metadata_source_lineage` VALUES
  ('DS-01', 'Olist Public', 'raw_olist_*', ['customers', 'orders', 'products'], 120000000, 148000, 'CC0', CURRENT_TIMESTAMP(), '2024-01-01', '{...}'),
  ('DS-02', 'UCI ML', 'raw_uci_*', ['orders', 'products'], 43000000, 45000, 'CC0', CURRENT_TIMESTAMP(), '2024-01-01', '{...}'),
  ('DS-03', 'Synthetic Customers', 'raw_customers_synthetic', ['customers', 'accounts'], 28000000, 500, 'Internal', CURRENT_TIMESTAMP(), 'Synthetic', '{...}'),
  -- ... remaining sources
;
```

### 6.2 Data Dictionary (Metadata Export)

```bash
# Export schema for all curated tables
for table in customers products accounts orders order_items payments refunds inventory_events support_tickets sla_config marketing_interactions employees teams task_queue_items; do
  bq show --schema --format=prettyjson {{PROJECT_ID}}:curated_retail_campaign.$table > /tmp/schema_${table}.json
done

# Publish to GCS for documentation
gsutil cp /tmp/schema_*.json gs://amg-campaign-corpus-q3/metadata/schemas/
```

---

## 7. Data Loading Checklist

### 7.1 Pre-Load Validation

| Item | Status | Owner | Sign-Off |
|------|--------|-------|----------|
| BigQuery datasets exist (raw, curated) | ☐ | Data Lead | ☐ |
| Source data available (public URLs or synthetic generation ready) | ☐ | Data Lead | ☐ |
| Transformation SQL validated (syntax + logic) | ☐ | Data Lead | ☐ |
| GCS staging bucket ready (amg-campaign-corpus-q3/sources/) | ☐ | Infrastructure Lead | ☐ |
| Service account has BigQuery write permissions | ☐ | Security Lead | ☐ |

### 7.2 Load Execution Checklist

| Task | Day | Status | Rows Loaded | Size (MB) | Owner | Sign-Off |
|------|-----|--------|------------|-----------|-------|----------|
| Download Olist data | 1 | ☐ | ~148K | 120 | Data Lead | ☐ |
| Download UCI data | 1 | ☐ | ~45K | 43 | Data Lead | ☐ |
| Generate synthetic customers (DS-03) | 2 | ☐ | 500 | 28 | Data Lead | ☐ |
| Generate synthetic orders (DS-04) | 2 | ☐ | 5K | 34 | Data Lead | ☐ |
| Generate synthetic events (DS-05) | 2 | ☐ | 3.5K | 18 | Data Lead | ☐ |
| Generate synthetic support (DS-06) | 2 | ☐ | 1.2K | 12 | Data Lead | ☐ |
| Transform to curated layer | 3 | ☐ | ~30K | 25 | Data Lead | ☐ |
| Verify lineage metadata | 3 | ☐ | — | — | Data Lead | ☐ |

### 7.3 Post-Load Validation

| Validation | Query | Expected | Status |
|-----------|-------|----------|--------|
| Raw table count | `SELECT COUNT(*) FROM raw_olist_orders` | ~100K | ☐ |
| Curated customer dedup | `SELECT COUNT(DISTINCT customer_id) FROM customers` | ~500 | ☐ |
| Foreign key integrity | Check for orphaned order_ids | 0 orphans | ☐ |
| Null checks | `SELECT COUNT(*) FROM orders WHERE order_id IS NULL` | 0 nulls | ☐ |
| Date range validity | `SELECT MIN(order_date), MAX(order_date) FROM orders` | 2024-01-01 to 2024-12-31 | ☐ |
| Cost reconciliation | `SELECT SUM(total_amount) FROM orders` | Match expected aggregate | ☐ |

---

## 8. Cost Estimate (E6-T1)

| Resource | Quantity | Unit Cost | Total |
|----------|----------|-----------|-------|
| BigQuery Storage (raw) | 6 GB | $0.025/GB/month | $0.15 |
| BigQuery Storage (curated) | 25 GB | $0.025/GB/month | $0.63 |
| BigQuery Query (load + transform) | ~50 GB scanned | $7.50/TB | $0.38 |
| GCS Storage (staging) | 300 MB | $0.020/GB/month | $0.01 |
| **Total (E6-T1)** | — | — | **~$1.17** |

**Budget Impact:** Week 5 BigQuery allocation: $35 (includes T1–T4); $1.17 utilization at T1 completion

---

## 9. Sign-Off

| Role | Owner | Sign-Off | Date |
|------|-------|----------|------|
| Data Lead | J. Patel | ☐ | ____ |
| Infrastructure Lead | T. Chen | ☐ | ____ |
| Program Manager | S. Gupta | ☐ | ____ |
