# E3-T1 — Canonical Schema Map for Retail Domains

**Epic:** E3 — Data Design, Fixtures, and Provenance Preparation
**Task:** E3-T1
**Date:** 2026-07-08
**Status:** Approved — FROZEN after Week 2 gate
**Owner:** MLE Lead

---

## 1. Domain Inventory

| Domain | BigQuery Dataset Target | Primary Use | Agents Using |
|--------|------------------------|-------------|-------------|
| Customers and Accounts | `curated_retail_campaign` | Customer identity, consent, segmentation | AGENT-CC, AGENT-EC, AGENT-TA |
| Products and Pricing | `curated_retail_campaign` | Product catalog, hierarchy, pricing | AGENT-CC, AGENT-EC, AGENT-CA |
| Orders and Items | `curated_retail_campaign` | Order history, line items, fulfillment | AGENT-CC, AGENT-TA |
| Payments and Refunds | `curated_retail_campaign` | Payment records, refund events | AGENT-TA (restricted) |
| Inventory and Fulfillment | `curated_retail_campaign` | Stock levels, warehouse events | AGENT-EC, AGENT-TA |
| Support Tickets and SLA | `curated_retail_campaign` | Ticket lifecycle, SLA adherence | AGENT-CC, AGENT-EC, AGENT-TA |
| Marketing Interactions | `curated_retail_campaign` | Campaign events, consent flags | AGENT-EC |
| Employees and Task Queues | `curated_retail_campaign` | Internal workforce, queue metadata | AGENT-EC, AGENT-TA |
| Raw ingestion (all domains) | `raw_retail_public` | Source-of-truth; not queried by agents | ETL/DQ pipelines only |
| Benchmark metrics | `benchmark_metrics` | Run results, KPI tracking | AGENT-CA (read), runtime (write) |

---

## 2. Table Schemas

### 2.1 `customers`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `customer_id` | STRING(36) | No | UUID primary key |
| `account_id` | STRING(36) | No | FK → `accounts.account_id` |
| `first_name` | STRING(100) | No | Synthetic first name |
| `last_name` | STRING(100) | No | Synthetic last name |
| `email` | STRING(255) | No | Synthetic email |
| `phone` | STRING(30) | Yes | Synthetic phone |
| `country_code` | STRING(2) | No | ISO 3166-1 alpha-2 |
| `segment` | STRING(50) | Yes | e.g. `premium`, `standard`, `at_risk` |
| `consent_marketing` | BOOL | No | Consent for marketing comms |
| `consent_data_processing` | BOOL | No | GDPR/CCPA consent flag |
| `created_at` | TIMESTAMP | No | |
| `updated_at` | TIMESTAMP | No | |

### 2.2 `accounts`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `account_id` | STRING(36) | No | UUID primary key |
| `account_type` | STRING(50) | No | `individual`, `business` |
| `status` | STRING(20) | No | `active`, `suspended`, `closed` |
| `tier` | STRING(20) | Yes | `bronze`, `silver`, `gold`, `platinum` |
| `created_at` | TIMESTAMP | No | |

### 2.3 `products`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `product_id` | STRING(36) | No | UUID primary key |
| `sku` | STRING(100) | No | Stock keeping unit |
| `name` | STRING(500) | No | Product display name |
| `category_l1` | STRING(100) | No | Top-level category |
| `category_l2` | STRING(100) | Yes | Sub-category |
| `category_l3` | STRING(100) | Yes | Leaf category |
| `brand` | STRING(200) | Yes | Brand name |
| `unit_price` | NUMERIC(10,2) | No | Current list price in USD |
| `weight_kg` | FLOAT64 | Yes | Physical weight |
| `is_active` | BOOL | No | Catalog visibility |
| `created_at` | TIMESTAMP | No | |

### 2.4 `orders`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `order_id` | STRING(36) | No | UUID primary key |
| `customer_id` | STRING(36) | No | FK → `customers.customer_id` |
| `account_id` | STRING(36) | No | FK → `accounts.account_id` |
| `status` | STRING(30) | No | `pending`, `confirmed`, `shipped`, `delivered`, `cancelled`, `returned` |
| `channel` | STRING(30) | No | `web`, `mobile`, `marketplace`, `in_store` |
| `currency` | STRING(3) | No | ISO 4217 |
| `total_amount` | NUMERIC(12,2) | No | Order total |
| `discount_amount` | NUMERIC(10,2) | No | Total discount applied |
| `shipping_country` | STRING(2) | No | |
| `placed_at` | TIMESTAMP | No | Order creation time |
| `updated_at` | TIMESTAMP | No | |
| `delivered_at` | TIMESTAMP | Yes | Null until delivery confirmed |

### 2.5 `order_items`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `order_item_id` | STRING(36) | No | UUID primary key |
| `order_id` | STRING(36) | No | FK → `orders.order_id` |
| `product_id` | STRING(36) | No | FK → `products.product_id` |
| `quantity` | INT64 | No | Units ordered |
| `unit_price` | NUMERIC(10,2) | No | Price at time of order |
| `discount_pct` | FLOAT64 | No | Item-level discount percentage |
| `fulfillment_status` | STRING(30) | No | `pending`, `picking`, `shipped`, `delivered` |

### 2.6 `payments`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `payment_id` | STRING(36) | No | UUID primary key |
| `order_id` | STRING(36) | No | FK → `orders.order_id` |
| `method` | STRING(30) | No | `credit_card`, `debit_card`, `wallet`, `bank_transfer` |
| `status` | STRING(20) | No | `pending`, `authorized`, `captured`, `failed`, `refunded` |
| `amount` | NUMERIC(12,2) | No | Payment amount |
| `currency` | STRING(3) | No | |
| `gateway_ref` | STRING(100) | Yes | External gateway transaction ID (masked/tokenized) |
| `processed_at` | TIMESTAMP | No | |

### 2.7 `refunds`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `refund_id` | STRING(36) | No | UUID primary key |
| `order_id` | STRING(36) | No | FK → `orders.order_id` |
| `payment_id` | STRING(36) | No | FK → `payments.payment_id` |
| `reason` | STRING(100) | No | `damaged`, `wrong_item`, `not_received`, `quality_issue`, `changed_mind` |
| `amount` | NUMERIC(12,2) | No | Refund amount |
| `status` | STRING(20) | No | `requested`, `approved`, `processed`, `rejected` |
| `requested_at` | TIMESTAMP | No | |
| `processed_at` | TIMESTAMP | Yes | |

### 2.8 `inventory_events`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `event_id` | STRING(36) | No | UUID primary key |
| `product_id` | STRING(36) | No | FK → `products.product_id` |
| `warehouse_id` | STRING(36) | No | Warehouse identifier |
| `event_type` | STRING(30) | No | `restock`, `pick`, `ship`, `return`, `adjustment` |
| `quantity_delta` | INT64 | No | Positive (in) or negative (out) |
| `quantity_after` | INT64 | No | Stock level after event |
| `occurred_at` | TIMESTAMP | No | |

### 2.9 `support_tickets`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `ticket_id` | STRING(36) | No | UUID primary key |
| `customer_id` | STRING(36) | No | FK → `customers.customer_id` |
| `order_id` | STRING(36) | Yes | FK → `orders.order_id` (null for non-order issues) |
| `category` | STRING(50) | No | `delivery`, `billing`, `product_quality`, `account`, `returns`, `other` |
| `priority` | STRING(10) | No | `low`, `medium`, `high`, `critical` |
| `status` | STRING(20) | No | `open`, `in_progress`, `pending_customer`, `resolved`, `closed` |
| `channel` | STRING(20) | No | `email`, `chat`, `phone`, `social` |
| `subject` | STRING(500) | No | Ticket subject (synthetic text) |
| `created_at` | TIMESTAMP | No | |
| `resolved_at` | TIMESTAMP | Yes | |
| `sla_due_at` | TIMESTAMP | No | Computed from priority SLA config |
| `sla_breached` | BOOL | No | |

### 2.10 `sla_config`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `priority` | STRING(10) | No | PK — matches `support_tickets.priority` |
| `response_sla_hours` | INT64 | No | Max hours to first response |
| `resolution_sla_hours` | INT64 | No | Max hours to resolution |

### 2.11 `marketing_interactions`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `interaction_id` | STRING(36) | No | UUID primary key |
| `customer_id` | STRING(36) | No | FK → `customers.customer_id` |
| `campaign_id` | STRING(36) | No | Marketing campaign identifier |
| `channel` | STRING(30) | No | `email`, `push`, `sms`, `display` |
| `event_type` | STRING(20) | No | `sent`, `opened`, `clicked`, `converted`, `unsubscribed` |
| `occurred_at` | TIMESTAMP | No | |

### 2.12 `employees`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `employee_id` | STRING(36) | No | UUID primary key |
| `team_id` | STRING(36) | No | FK → `teams.team_id` |
| `name` | STRING(200) | No | Synthetic full name |
| `role` | STRING(100) | No | e.g. `support_agent`, `team_lead`, `engineer` |
| `department` | STRING(100) | No | |
| `is_active` | BOOL | No | |
| `hired_at` | DATE | No | |

### 2.13 `teams`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `team_id` | STRING(36) | No | UUID primary key |
| `name` | STRING(200) | No | Team display name |
| `department` | STRING(100) | No | |
| `lead_employee_id` | STRING(36) | Yes | FK → `employees.employee_id` |

### 2.14 `task_queue_items`

| Column | Type | Nullable | Description |
|--------|------|---------|-------------|
| `task_id` | STRING(36) | No | UUID primary key |
| `queue_name` | STRING(100) | No | e.g. `support_tier1`, `returns_processing` |
| `assigned_employee_id` | STRING(36) | Yes | FK → `employees.employee_id` |
| `ticket_id` | STRING(36) | Yes | FK → `support_tickets.ticket_id` |
| `status` | STRING(20) | No | `queued`, `assigned`, `in_progress`, `completed`, `escalated` |
| `priority` | INT64 | No | Numeric priority (lower = higher priority) |
| `created_at` | TIMESTAMP | No | |
| `completed_at` | TIMESTAMP | Yes | |

---

## 3. Entity-Relationship Matrix

| From Entity | Relationship | To Entity | Cardinality | Mandatory |
|-------------|------------|-----------|------------|----------|
| `customers` | belongs to | `accounts` | N:1 | Yes |
| `orders` | placed by | `customers` | N:1 | Yes |
| `orders` | linked to | `accounts` | N:1 | Yes |
| `order_items` | belongs to | `orders` | N:1 | Yes |
| `order_items` | references | `products` | N:1 | Yes |
| `payments` | for | `orders` | N:1 | Yes |
| `refunds` | against | `orders` | N:1 | Yes |
| `refunds` | from | `payments` | N:1 | Yes |
| `inventory_events` | for | `products` | N:1 | Yes |
| `support_tickets` | raised by | `customers` | N:1 | Yes |
| `support_tickets` | related to | `orders` | N:1 | No (nullable) |
| `marketing_interactions` | for | `customers` | N:1 | Yes |
| `employees` | member of | `teams` | N:1 | Yes |
| `teams` | led by | `employees` | 1:1 | No (nullable) |
| `task_queue_items` | assigned to | `employees` | N:1 | No (nullable) |
| `task_queue_items` | resolves | `support_tickets` | N:1 | No (nullable) |

---

## 4. Scale Targets

| Table | Target Row Count | Approx Size | Seasonality |
|-------|----------------|-------------|-------------|
| `customers` | 500,000 | ~200 MB | — |
| `accounts` | 480,000 | ~80 MB | — |
| `products` | 50,000 | ~50 MB | — |
| `orders` | 2,000,000 | ~1.5 GB | Yes — weekly and seasonal spikes |
| `order_items` | 6,000,000 | ~3 GB | Follows orders |
| `payments` | 2,000,000 | ~800 MB | Follows orders |
| `refunds` | 120,000 | ~60 MB | ~6% of orders |
| `inventory_events` | 5,000,000 | ~2 GB | Restocks weekly; picks follow orders |
| `support_tickets` | 400,000 | ~500 MB | Spikes after seasonal order peaks |
| `sla_config` | 4 | <1 KB | — |
| `marketing_interactions` | 3,000,000 | ~1.5 GB | Campaign cadence |
| `employees` | 2,000 | ~1 MB | — |
| `teams` | 50 | <1 MB | — |
| `task_queue_items` | 500,000 | ~200 MB | Follows tickets |
| **Total (curated)** | **~20M rows** | **~12 GB** | |

Raw dataset in `raw_retail_public` mirrors the same volume before transformation.

---

## 5. Benchmark Metrics Schema

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | STRING(100) | Benchmark run identifier (from run manifest) |
| `scenario_id` | STRING(50) | Scenario from benchmark catalog |
| `agent_id` | STRING(20) | Agent profile identifier |
| `baseline_id` | STRING(50) | Baseline method identifier |
| `started_at` | TIMESTAMP | Run start |
| `completed_at` | TIMESTAMP | Run end |
| `success` | BOOL | Pass/fail per scoring rubric |
| `groundedness_score` | FLOAT64 | Supported claims / total material claims |
| `latency_ms` | INT64 | End-to-end latency in milliseconds |
| `cost_usd` | FLOAT64 | Estimated cost for this run |
| `retry_count` | INT64 | Number of retries within the run |
| `evidence_node_count` | INT64 | Graph nodes cited as evidence |
| `failure_code` | STRING(100) | Null if success; taxonomy code if failed |
| `config_hash` | STRING(64) | SHA-256 of run configuration |
| `model_version` | STRING(100) | Vertex AI model version used |
| `prompt_version` | STRING(50) | Prompt template version |
| `seed` | INT64 | Random seed for reproducibility |
| `warm_up` | BOOL | True if warm-up run (excluded from scoring) |
| `notes` | STRING(1000) | Optional run notes |
