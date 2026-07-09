# E6-T3 — Spanner Graph Seeding and Validation

**Epic:** E6 — Cloud Data Provisioning and Integration Bring-up
**Task:** E6-T3
**Date:** 2026-07-18
**Status:** Approved
**Owner:** Data Lead

---

## 1. Objective

Provision Spanner graph structures (11 migrations, memory_db database) and seed with 239 foundational nodes and ~400 edges from E3-T4 frozen specification. Validate tripartite memory tier separation (T1 Context, T2 Semantic, T3 Audit) and test idempotent MERGE operations.

**Dependencies:** E3-T4 (graph schema), E5-T8 (Spanner instance created), E6-T1 (curated data available for reference)

---

## 2. Spanner Database Architecture (Frozen from E3-T4)

### 2.1 Tripartite Memory Model

```
memory_db (11 migrations applied)
├── T1: Context Memory (short-term, volatile)
│   └── Nodes: Customer, Order, Account, Product (recent context)
│   └── TTL: Session-scoped (auto-purge after 24h)
│   └── Access: Read/Write by agents
│
├── T2: Semantic Memory (long-term, persistent)
│   └── Nodes: Customer, Account, Team, Document, IntegrationEvent (enriched)
│   └── Properties: cognitive_weight, last_accessed (for prioritization)
│   └── TTL: Indefinite (campaign-scoped)
│   └── Access: Read by agents, append-only writes
│
└── T3: Audit Memory (immutable log)
    └── Nodes: All operations recorded (agent_execution, decision, evidence_retrieval)
    └── Properties: Immutable; append-only enforcement
    └── TTL: Indefinite (compliance-scoped)
    └── Access: Append by audit sink, read by compliance queries
```

### 2.2 Node Labels (9 Total)

| Label | Count | Example | Tier |
|-------|-------|---------|------|
| **Customer** | 50 | CUST-00001 | T1, T2 |
| **Account** | 30 | ACCT-00001 | T1, T2 |
| **Product** | 35 | PROD-00001 | T2 |
| **Order** | 40 | ORD-00001 | T1 |
| **Ticket** | 25 | TKT-00001 | T1, T2 |
| **Agent** | 8 | AGENT-campaign-001 | T2, T3 |
| **Team** | 6 | TEAM-data-science | T2 |
| **IntegrationEvent** | 10 | EVT-webhook-001 | T2, T3 |
| **Document** | 35 | DOC-c01-001 | T2 |
| **TOTAL** | **239** | — | — |

### 2.3 Edge Labels (11 Total)

| Label | Source | Target | Count | Example |
|-------|--------|--------|-------|---------|
| **CUSTOMER_PLACED_ORDER** | Customer | Order | 80 | — |
| **CUSTOMER_OPENED_TICKET** | Customer | Ticket | 25 | — |
| **ORDER_CONTAINS_PRODUCT** | Order | Product | 200 | — |
| **AGENT_MEMBER_OF_TEAM** | Agent | Team | 16 | — |
| **AGENT_RESOLVED_TICKET** | Agent | Ticket | 20 | — |
| **DOCUMENT_REFERENCES_PRODUCT** | Document | Product | 60 | — |
| **INTEGRATION_EVENT_MENTIONS_CUSTOMER** | IntegrationEvent | Customer | 30 | — |
| **TICKET_RELATES_TO_ORDER** | Ticket | Order | 15 | — |
| **ACCOUNT_CONTAINS_CUSTOMER** | Account | Customer | 30 | — |
| **TEAM_SUPPORTS_PRODUCT** | Team | Product | 20 | — |
| **DOCUMENT_SUPPLEMENTS_TEAM_KNOWLEDGE** | Document | Team | 12 | — |
| **TOTAL** | — | — | **~508** | — |

---

## 3. Database Schema Review (11 Migrations)

### 3.1 Migration Sequence

| # | Migration | Purpose | Tables/Views | Status |
|---|-----------|---------|--------------|--------|
| 1 | 001_memory_node_table.sql | Create core node table | memory_nodes | ✓ Applied |
| 2 | 002_memory_edge_table.sql | Create edge table | memory_edges | ✓ Applied |
| 3 | 003_property_graph.sql | Denormalized view for traversal | property_graph | ✓ Applied |
| 4 | 004_add_tenant_id.sql | Tenant isolation | memory_nodes.tenant_id | ✓ Applied |
| 5 | 005_audit_immutability_controls.sql | T3 append-only enforcement | audit_immutability | ✓ Applied |
| 6 | 006_add_session_action_count.sql | Track session operations | session_action_count | ✓ Applied |
| 7 | 007_property_graph_session_action_count.sql | Session-scoped view | property_graph_session | ✓ Applied |
| 8 | 008_add_engram_evidence_table.sql | Confidence metadata | engram_evidence | ✓ Applied |
| 9 | 009_add_confidence_metadata.sql | Evidence scoring | confidence_score | ✓ Applied |
| 10 | 010_enforce_composite_pk_application_guard.sql | Multi-tenant guard | composite_pk_check | ✓ Applied |
| 11 | 011_session_lifecycle_columns.sql | Session state tracking | session_state | ✓ Applied |

### 3.2 Core Table Schemas

**memory_nodes:**
```sql
CREATE TABLE memory_nodes (
  node_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  label STRING NOT NULL,  -- Customer, Order, Product, etc.
  properties JSONB,
  cognitive_weight NUMERIC,  -- 0.0–1.0 (importance for retrieval)
  last_accessed TIMESTAMP,
  memory_tier STRING,  -- T1, T2, T3
  session_id STRING,  -- T1 session scoping
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  PRIMARY KEY (tenant_id, node_id)
) INTERLEAVE IN PARENT campaigns;
```

**memory_edges:**
```sql
CREATE TABLE memory_edges (
  edge_id STRING NOT NULL,
  tenant_id STRING NOT NULL,
  source_node_id STRING NOT NULL,
  target_node_id STRING NOT NULL,
  label STRING NOT NULL,  -- CUSTOMER_PLACED_ORDER, etc.
  properties JSONB,
  cognitive_weight NUMERIC,
  last_accessed TIMESTAMP,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  PRIMARY KEY (tenant_id, edge_id),
  FOREIGN KEY (tenant_id, source_node_id) REFERENCES memory_nodes,
  FOREIGN KEY (tenant_id, target_node_id) REFERENCES memory_nodes
) INTERLEAVE IN PARENT campaigns;
```

---

## 4. Seed Data Specification (Frozen from E3-T4)

### 4.1 Node Seed (239 Nodes)

**Customers (50 nodes):**
```json
[
  {
    "node_id": "CUST-00001",
    "label": "Customer",
    "properties": {
      "email": "customer1@example.com",
      "name": "Alice Johnson",
      "created_at": "2024-01-15",
      "lifetime_value": 1250.50,
      "country": "US"
    },
    "memory_tier": "T1",
    "cognitive_weight": 0.85
  },
  {
    "node_id": "CUST-00002",
    "label": "Customer",
    "properties": {
      "email": "customer2@example.com",
      "name": "Bob Smith",
      "created_at": "2024-02-20",
      "lifetime_value": 850.00,
      "country": "BR"
    },
    "memory_tier": "T2",
    "cognitive_weight": 0.65
  }
]
```

**Products (35 nodes):**
```json
[
  {
    "node_id": "PROD-00001",
    "label": "Product",
    "properties": {
      "sku": "LAPTOP-DELL-001",
      "name": "Dell Inspiron 15",
      "category": "Electronics",
      "price": 799.99,
      "stock": 45
    },
    "memory_tier": "T2",
    "cognitive_weight": 0.92
  }
]
```

**Orders (40 nodes):**
```json
[
  {
    "node_id": "ORD-00001",
    "label": "Order",
    "properties": {
      "order_number": "ORD-2024-001",
      "customer_id": "CUST-00001",
      "order_date": "2024-03-10",
      "total_amount": 1250.50,
      "status": "delivered"
    },
    "memory_tier": "T1",
    "cognitive_weight": 0.70
  }
]
```

**Support Tickets (25 nodes):**
```json
[
  {
    "node_id": "TKT-00001",
    "label": "Ticket",
    "properties": {
      "ticket_id": "TKT-2024-001",
      "customer_id": "CUST-00001",
      "subject": "Shipping delay",
      "created_at": "2024-03-11",
      "resolved_at": "2024-03-13",
      "priority": "medium"
    },
    "memory_tier": "T1",
    "cognitive_weight": 0.55
  }
]
```

(Similar JSON structures for Accounts, Agents, Teams, IntegrationEvents, Documents)

### 4.2 Edge Seed (~400–508 Edges)

**CUSTOMER_PLACED_ORDER (80 edges):**
```json
[
  {
    "edge_id": "CUST-CUST-00001-ORD-00001",
    "source_node_id": "CUST-00001",
    "target_node_id": "ORD-00001",
    "label": "CUSTOMER_PLACED_ORDER",
    "properties": {
      "placed_at": "2024-03-10T14:30:00Z"
    },
    "cognitive_weight": 0.90
  }
]
```

**ORDER_CONTAINS_PRODUCT (200 edges):**
```json
[
  {
    "edge_id": "ORD-ORD-00001-PROD-00001",
    "source_node_id": "ORD-00001",
    "target_node_id": "PROD-00001",
    "label": "ORDER_CONTAINS_PRODUCT",
    "properties": {
      "quantity": 1,
      "unit_price": 799.99,
      "line_item_total": 799.99
    },
    "cognitive_weight": 0.85
  }
]
```

(Similar JSON structures for remaining edge types)

---

## 5. Seeding Pipeline

### 5.1 Idempotent MERGE Statements

**Node MERGE (safe for replay):**

```sql
-- Upsert nodes idempotently
MERGE INTO memory_nodes AS t
USING (
  SELECT
    @node_id AS node_id,
    @tenant_id AS tenant_id,
    @label AS label,
    PARSE_JSON(@properties) AS properties,
    CAST(@cognitive_weight AS NUMERIC) AS cognitive_weight,
    CURRENT_TIMESTAMP() AS last_accessed,
    @memory_tier AS memory_tier,
    @session_id AS session_id,
    CURRENT_TIMESTAMP() AS created_at,
    CURRENT_TIMESTAMP() AS updated_at
) AS s
ON t.tenant_id = s.tenant_id AND t.node_id = s.node_id
WHEN MATCHED THEN
  UPDATE SET
    properties = s.properties,
    cognitive_weight = s.cognitive_weight,
    last_accessed = s.last_accessed,
    updated_at = s.updated_at
WHEN NOT MATCHED THEN
  INSERT (
    node_id, tenant_id, label, properties, cognitive_weight,
    last_accessed, memory_tier, session_id, created_at, updated_at
  )
  VALUES (
    s.node_id, s.tenant_id, s.label, s.properties, s.cognitive_weight,
    s.last_accessed, s.memory_tier, s.session_id, s.created_at, s.updated_at
  );
```

**Edge MERGE (safe for replay):**

```sql
MERGE INTO memory_edges AS t
USING (
  SELECT
    @edge_id AS edge_id,
    @tenant_id AS tenant_id,
    @source_node_id AS source_node_id,
    @target_node_id AS target_node_id,
    @label AS label,
    PARSE_JSON(@properties) AS properties,
    CAST(@cognitive_weight AS NUMERIC) AS cognitive_weight,
    CURRENT_TIMESTAMP() AS last_accessed,
    CURRENT_TIMESTAMP() AS created_at,
    CURRENT_TIMESTAMP() AS updated_at
) AS s
ON t.tenant_id = s.tenant_id AND t.edge_id = s.edge_id
WHEN MATCHED THEN
  UPDATE SET
    properties = s.properties,
    cognitive_weight = s.cognitive_weight,
    last_accessed = s.last_accessed,
    updated_at = s.updated_at
WHEN NOT MATCHED THEN
  INSERT (
    edge_id, tenant_id, source_node_id, target_node_id, label,
    properties, cognitive_weight, last_accessed, created_at, updated_at
  )
  VALUES (
    s.edge_id, s.tenant_id, s.source_node_id, s.target_node_id, s.label,
    s.properties, s.cognitive_weight, s.last_accessed, s.created_at, s.updated_at
  );
```

### 5.2 Seeding Execution (Python)

```python
# seed_spanner_graph.py
import json
from google.cloud import spanner

PROJECT_ID = "amg-validation-2026-07-q3"
INSTANCE_ID = "amg-campaign-spanner"
DATABASE_ID = "memory_db"
TENANT_ID = "campaign-validation-2026-q3"

def seed_graph():
    """Load seed nodes and edges from JSON files."""
    client = spanner.Client(project=PROJECT_ID)
    instance = client.instance(INSTANCE_ID)
    database = instance.database(DATABASE_ID)

    # Load seed data
    with open('seed_nodes.json', 'r') as f:
        nodes = json.load(f)

    with open('seed_edges.json', 'r') as f:
        edges = json.load(f)

    node_count = 0
    edge_count = 0

    def insert_nodes(transaction):
        nonlocal node_count
        for node in nodes:
            transaction.execute_update(
                """
                MERGE INTO memory_nodes AS t
                USING (SELECT @1 AS node_id, @2 AS tenant_id, @3 AS label,
                              PARSE_JSON(@4) AS properties, CAST(@5 AS NUMERIC) AS cognitive_weight,
                              CURRENT_TIMESTAMP() AS last_accessed, @6 AS memory_tier,
                              @7 AS session_id, CURRENT_TIMESTAMP() AS created_at,
                              CURRENT_TIMESTAMP() AS updated_at) AS s
                ON t.tenant_id = s.tenant_id AND t.node_id = s.node_id
                WHEN MATCHED THEN UPDATE SET
                  properties = s.properties,
                  cognitive_weight = s.cognitive_weight,
                  last_accessed = s.last_accessed,
                  updated_at = s.updated_at
                WHEN NOT MATCHED THEN INSERT (
                  node_id, tenant_id, label, properties, cognitive_weight,
                  last_accessed, memory_tier, session_id, created_at, updated_at
                )
                VALUES (
                  s.node_id, s.tenant_id, s.label, s.properties, s.cognitive_weight,
                  s.last_accessed, s.memory_tier, s.session_id, s.created_at, s.updated_at
                )
                """,
                [
                    node['node_id'],
                    TENANT_ID,
                    node['label'],
                    json.dumps(node['properties']),
                    node.get('cognitive_weight', 0.5),
                    node.get('memory_tier', 'T2'),
                    node.get('session_id', None)
                ]
            )
            node_count += 1

    def insert_edges(transaction):
        nonlocal edge_count
        for edge in edges:
            transaction.execute_update(
                """
                MERGE INTO memory_edges AS t
                USING (SELECT @1 AS edge_id, @2 AS tenant_id, @3 AS source_node_id,
                              @4 AS target_node_id, @5 AS label,
                              PARSE_JSON(@6) AS properties, CAST(@7 AS NUMERIC) AS cognitive_weight,
                              CURRENT_TIMESTAMP() AS last_accessed, CURRENT_TIMESTAMP() AS created_at,
                              CURRENT_TIMESTAMP() AS updated_at) AS s
                ON t.tenant_id = s.tenant_id AND t.edge_id = s.edge_id
                WHEN MATCHED THEN UPDATE SET
                  properties = s.properties,
                  cognitive_weight = s.cognitive_weight,
                  last_accessed = s.last_accessed,
                  updated_at = s.updated_at
                WHEN NOT MATCHED THEN INSERT (
                  edge_id, tenant_id, source_node_id, target_node_id, label,
                  properties, cognitive_weight, last_accessed, created_at, updated_at
                )
                VALUES (
                  s.edge_id, s.tenant_id, s.source_node_id, s.target_node_id, s.label,
                  s.properties, s.cognitive_weight, s.last_accessed, s.created_at, s.updated_at
                )
                """,
                [
                    edge['edge_id'],
                    TENANT_ID,
                    edge['source_node_id'],
                    edge['target_node_id'],
                    edge['label'],
                    json.dumps(edge['properties']),
                    edge.get('cognitive_weight', 0.5)
                ]
            )
            edge_count += 1

    # Execute seeding transactions
    database.run_in_transaction(insert_nodes)
    print(f"✓ Seeded {node_count} nodes")

    database.run_in_transaction(insert_edges)
    print(f"✓ Seeded {edge_count} edges")

    return node_count, edge_count

if __name__ == "__main__":
    nodes, edges = seed_graph()
    print(f"\nSeed Complete: {nodes} nodes + {edges} edges")
```

---

## 6. No-Evidence Fixtures (Frozen from E3-T4)

**5 fixed no-evidence fixtures** (for E4 retrieval scenarios with grounded "no evidence" behavior):

```json
{
  "no_evidence_fixtures": [
    {
      "fixture_id": "NE-001",
      "scenario": "E4-S1 (Product Inquiry)",
      "query": "What is the maximum resolution of the SuperCam Pro 8000?",
      "expected_behavior": "Agent retrieves corpus docs for 'SuperCam Pro 8000' and 'resolution'; expects 0 results (product not in corpus)",
      "expected_response": "I don't have information about the SuperCam Pro 8000 in my knowledge base. Please contact support.",
      "memory_state": {
        "retrieved_docs": [],
        "graph_traversal_hops": 0,
        "confidence_score": 0.0
      }
    },
    {
      "fixture_id": "NE-002",
      "scenario": "E4-S2 (Policy Lookup)",
      "query": "Can I return items after 180 days?",
      "expected_behavior": "Agent searches support_policies in memory and corpus; finds partial match (only 30-day policy mentioned)",
      "expected_response": "Our standard return window is 30 days from purchase. For exceptions, please contact support.",
      "memory_state": {
        "retrieved_docs": ["C-03-045"],
        "graph_traversal_hops": 2,
        "confidence_score": 0.65
      }
    },
    {
      "fixture_id": "NE-003",
      "scenario": "E4-S4 (Integration Error)",
      "query": "How do I configure Webhook v3.2 for order events?",
      "expected_behavior": "Agent searches API docs for 'Webhook v3.2'; version not in corpus (only v2.1 documented)",
      "expected_response": "I found documentation for Webhook v2.1, but not v3.2. The API may have been updated. Please check our latest developer docs.",
      "memory_state": {
        "retrieved_docs": ["C-02-120"],
        "graph_traversal_hops": 1,
        "confidence_score": 0.40
      }
    },
    {
      "fixture_id": "NE-004",
      "scenario": "E4-S5 (Cross-Domain Reasoning)",
      "query": "What payment methods does ACME Corp prefer for B2B orders?",
      "expected_behavior": "Agent searches for ACME Corp customer node; found in T2 memory (customer exists), but no PAYMENT_PREFERENCE edge",
      "expected_response": "I can see ACME Corp in our customer records, but I don't have their payment preferences documented. I'll check with the account manager.",
      "memory_state": {
        "retrieved_docs": [],
        "graph_traversal_hops": 1,
        "confidence_score": 0.50,
        "graph_node_found": "ACCT-00042"
      }
    },
    {
      "fixture_id": "NE-005",
      "scenario": "E4-S3 (Ambiguous Ticket Context)",
      "query": "Customer mentioned 'the issue' but I don't know which product. Can you help?",
      "expected_behavior": "Agent retrieves customer's recent order history; finds multiple orders (ambiguity), cannot disambiguate",
      "expected_response": "The customer has multiple recent orders. Could you clarify which product is having issues, or I can escalate to get more context.",
      "memory_state": {
        "retrieved_docs": [],
        "graph_traversal_hops": 2,
        "confidence_score": 0.35,
        "ambiguity_flag": true
      }
    }
  ]
}
```

---

## 7. Validation Queries

### 7.1 Post-Seeding Verification

```sql
-- Verify node counts by label
SELECT label, COUNT(*) AS count
FROM memory_nodes
WHERE tenant_id = 'campaign-validation-2026-q3'
GROUP BY label
ORDER BY count DESC;

-- Expected output:
-- Customer        | 50
-- Order           | 40
-- Product         | 35
-- Document        | 35
-- Account         | 30
-- Ticket          | 25
-- Agent           | 8
-- Team            | 6
-- IntegrationEvent| 10
-- TOTAL           | 239

-- Verify edge counts by label
SELECT label, COUNT(*) AS count
FROM memory_edges
WHERE tenant_id = 'campaign-validation-2026-q3'
GROUP BY label
ORDER BY count DESC;

-- Expected output:
-- ORDER_CONTAINS_PRODUCT          | 200
-- CUSTOMER_PLACED_ORDER           | 80
-- DOCUMENT_REFERENCES_PRODUCT     | 60
-- INTEGRATION_EVENT_MENTIONS_CUSTOMER | 30
-- ACCOUNT_CONTAINS_CUSTOMER       | 30
-- AGENT_MEMBER_OF_TEAM            | 16
-- CUSTOMER_OPENED_TICKET          | 25
-- AGENT_RESOLVED_TICKET           | 20
-- TEAM_SUPPORTS_PRODUCT           | 20
-- DOCUMENT_SUPPLEMENTS_TEAM_KNOWLEDGE | 12
-- TICKET_RELATES_TO_ORDER         | 15
-- TOTAL                           | ~508

-- Verify memory tier distribution
SELECT memory_tier, COUNT(*) AS count
FROM memory_nodes
WHERE tenant_id = 'campaign-validation-2026-q3'
GROUP BY memory_tier;

-- Expected: T1 ~120, T2 ~119

-- Verify no orphaned edges
SELECT COUNT(*) AS orphan_edges
FROM memory_edges e
LEFT JOIN memory_nodes n_src
  ON e.tenant_id = n_src.tenant_id AND e.source_node_id = n_src.node_id
WHERE e.tenant_id = 'campaign-validation-2026-q3'
  AND n_src.node_id IS NULL;

-- Expected: 0

-- Verify cognitive weight distribution (should be 0.0–1.0)
SELECT
  MIN(cognitive_weight) AS min_weight,
  MAX(cognitive_weight) AS max_weight,
  AVG(cognitive_weight) AS avg_weight,
  COUNT(*) AS total_nodes
FROM memory_nodes
WHERE tenant_id = 'campaign-validation-2026-q3';

-- Expected: min=0.0, max=1.0, avg~0.6, count=239
```

### 7.2 Tripartite Tier Validation

```sql
-- Verify T1 Context nodes have session_id
SELECT COUNT(*) AS t1_with_session
FROM memory_nodes
WHERE tenant_id = 'campaign-validation-2026-q3'
  AND memory_tier = 'T1'
  AND session_id IS NOT NULL;

-- Expected: >80 (majority of T1 nodes have session scope)

-- Verify T3 Audit nodes are append-only (no updates after initial insert)
SELECT COUNT(*) AS t3_audit_nodes
FROM memory_nodes
WHERE tenant_id = 'campaign-validation-2026-q3'
  AND memory_tier = 'T3';

-- Expected: ~0–20 (T3 populated during audit events, not seeding)
```

---

## 8. Seeding Execution Plan

### 8.1 Day 1: Schema Validation and Node Seeding

```
09:00 — Verify all 11 migrations applied to memory_db
10:00 — Run seed_nodes.json through validation script
11:00 — Execute idempotent MERGE for all 239 nodes
12:00 — Verify node counts and cognitive weights
14:00 — CHECKPOINT: 239 nodes seeded and verified
```

### 8.2 Day 2: Edge Seeding and Relationship Validation

```
09:00 — Run seed_edges.json through validation script
10:00 — Execute idempotent MERGE for ~400–508 edges
11:00 — Verify no orphaned edges (all source/target nodes exist)
12:00 — Validate cognitive weight distribution
14:00 — CHECKPOINT: ~508 edges seeded; graph topology valid
```

### 8.3 Day 3: Tier Separation and No-Evidence Fixtures

```
09:00 — Verify T1/T2/T3 tier separation (session scoping, audit controls)
10:00 — Load 5 no-evidence fixtures into benchmark_metrics.no_evidence_fixtures (BigQuery)
11:00 — Test each fixture scenario (query simulation, expected response verification)
12:00 — Verify memory state and confidence scores for each fixture
14:00 — CHECKPOINT: Tripartite model validated; fixtures ready for E4 benchmark
```

---

## 9. Quality Checklist

| Check | Status | Expected | Owner |
|-------|--------|----------|-------|
| All 11 migrations applied | ☐ | 0 migration errors | Data Lead |
| 239 nodes seeded | ☐ | COUNT(nodes) = 239 | Data Lead |
| ~508 edges seeded | ☐ | COUNT(edges) ≥ 400 | Data Lead |
| No orphaned edges | ☐ | 0 orphan edges | Data Lead |
| T1/T2/T3 tier separation | ☐ | Nodes properly tagged | Data Lead |
| Cognitive weight valid range | ☐ | 0.0–1.0 range | Data Lead |
| No-evidence fixtures loaded | ☐ | 5 fixtures in BigQuery | Data Lead |
| Graph traversal sanity check | ☐ | Sample queries return results | Data Lead |

---

## 10. Cost Estimate (E6-T3)

| Resource | Quantity | Unit Cost | Total |
|----------|----------|-----------|-------|
| Spanner Storage (seed data) | ~50 MB | ~$0.18/GB/month | $0.009 |
| Spanner Write Operations | ~750 (nodes + edges) | ~$0.12 per million | $0.0001 |
| Spanner Read Operations | ~100 (validation) | ~$0.12 per million | $0.00001 |
| **Total (E6-T3)** | — | — | **~$0.01** |

**Budget Impact:** Week 5 Spanner allocation: $20; $0.01 utilization at T3 completion

---

## 11. Sign-Off

| Role | Owner | Sign-Off | Date |
|------|-------|----------|------|
| Data Lead | J. Patel | ☐ | ____ |
| Infrastructure Lead | T. Chen | ☐ | ____ |
| Program Manager | S. Gupta | ☐ | ____ |
