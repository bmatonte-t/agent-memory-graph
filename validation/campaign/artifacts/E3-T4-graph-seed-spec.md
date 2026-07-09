# E3-T4 — Spanner Graph Seed Specification and No-Evidence Fixtures

**Epic:** E3 — Data Design, Fixtures, and Provenance Preparation
**Task:** E3-T4
**Date:** 2026-07-08
**Status:** Approved
**Owner:** MLE Lead

---

## 1. Graph Model Overview

The Spanner property graph (`amg-campaign-db`) is the memory backbone for all AMG agents. It stores the organizational knowledge graph and is the primary grounding source for T2 (Semantic) memory retrieval.

### 1.1 Node Labels

| Node Label | Description | ID Property | Source |
|------------|-------------|------------|--------|
| `Customer` | External customer entity | `customer_id` (UUID) | Derived from `curated_retail_campaign.customers` |
| `Account` | Customer account | `account_id` (UUID) | Derived from `curated_retail_campaign.accounts` |
| `Product` | Product in catalog | `product_id` (UUID) | Derived from `curated_retail_campaign.products` |
| `Order` | Placed customer order | `order_id` (UUID) | Derived from `curated_retail_campaign.orders` |
| `Ticket` | Support ticket | `ticket_id` (UUID) | Derived from `curated_retail_campaign.support_tickets` |
| `Agent` | Internal support agent (employee) | `employee_id` (UUID) | Derived from `curated_retail_campaign.employees` |
| `Team` | Internal team | `team_id` (UUID) | Derived from `curated_retail_campaign.teams` |
| `IntegrationEvent` | External system event | `event_id` (UUID) | Synthetic (CORP-05 sourced) |
| `Document` | Corpus document reference | `document_id` (UUID) | GCS object path as ID |

### 1.2 Node Mandatory Properties

| Node Label | Mandatory Properties | Optional Properties |
|------------|--------------------|--------------------|
| `Customer` | `customer_id`, `segment`, `country_code`, `cognitive_weight`, `last_accessed` | `consent_marketing` |
| `Account` | `account_id`, `account_type`, `status`, `cognitive_weight`, `last_accessed` | `tier` |
| `Product` | `product_id`, `sku`, `name`, `category_l1`, `is_active`, `cognitive_weight`, `last_accessed` | `brand`, `unit_price` |
| `Order` | `order_id`, `status`, `channel`, `placed_at`, `cognitive_weight`, `last_accessed` | `delivered_at` |
| `Ticket` | `ticket_id`, `category`, `priority`, `status`, `sla_breached`, `cognitive_weight`, `last_accessed` | `resolved_at` |
| `Agent` | `employee_id`, `name`, `role`, `department`, `cognitive_weight`, `last_accessed` | |
| `Team` | `team_id`, `name`, `department`, `cognitive_weight`, `last_accessed` | |
| `IntegrationEvent` | `event_id`, `event_type`, `source_system`, `occurred_at`, `cognitive_weight`, `last_accessed` | `outcome` |
| `Document` | `document_id`, `corpus_type`, `gcs_path`, `sensitivity_class`, `cognitive_weight`, `last_accessed` | `domain` |

**All nodes must include:** `cognitive_weight FLOAT64 DEFAULT 0.5`, `last_accessed TIMESTAMP`

### 1.3 Edge Labels

| Edge Label | From Node | To Node | Description |
|------------|-----------|---------|-------------|
| `CUSTOMER_HAS_ACCOUNT` | Customer | Account | Account ownership |
| `CUSTOMER_PLACED_ORDER` | Customer | Order | Purchase relationship |
| `ORDER_CONTAINS_PRODUCT` | Order | Product | Order line item link |
| `CUSTOMER_OPENED_TICKET` | Customer | Ticket | Support relationship |
| `ORDER_GENERATED_TICKET` | Order | Ticket | Order-specific support |
| `TICKET_REFERENCES_DOCUMENT` | Ticket | Document | Corpus grounding for ticket context |
| `AGENT_RESOLVED_TICKET` | Agent | Ticket | Resolution attribution |
| `AGENT_MEMBER_OF_TEAM` | Agent | Team | Team membership |
| `INTEGRATION_EVENT_RELATED_TO_ORDER` | IntegrationEvent | Order | Event-order linkage |
| `INTEGRATION_EVENT_RELATED_TO_TICKET` | IntegrationEvent | Ticket | Event-ticket linkage |
| `DOCUMENT_DESCRIBES_PRODUCT` | Document | Product | Manual-product linkage |

### 1.4 Edge Mandatory Properties

All edges must include:
- `created_at TIMESTAMP`
- `cognitive_weight FLOAT64 DEFAULT 0.5`

---

## 2. Seed Counts Target

| Node / Edge Label | Target Count | Isolated Node Allowance (<=5%) | Notes |
|-------------------|-------------|-------------------------------|-------|
| `Customer` | 10,000 | ≤500 isolated | Subset of full 500K; representative sample for graph traversal |
| `Account` | 9,500 | ≤475 isolated | ~5% customers share accounts |
| `Product` | 5,000 | ≤250 isolated | Subset of catalog; must include no-evidence products |
| `Order` | 30,000 | ≤1,500 isolated | ~3 orders per customer average |
| `Ticket` | 8,000 | ≤400 isolated | ~80% of orders have at least one ticket |
| `Agent` | 200 | 0 | All agents must belong to a team |
| `Team` | 10 | 0 | All teams must have at least 5 agents |
| `IntegrationEvent` | 2,000 | ≤100 isolated | |
| `Document` | 500 | ≤25 isolated | All corpus CORP-01 product manual references |
| `CUSTOMER_HAS_ACCOUNT` | 9,500 | — | |
| `CUSTOMER_PLACED_ORDER` | 30,000 | — | |
| `ORDER_CONTAINS_PRODUCT` | 75,000 | — | ~2.5 products per order |
| `CUSTOMER_OPENED_TICKET` | 8,000 | — | |
| `ORDER_GENERATED_TICKET` | 5,000 | — | 62.5% of tickets linked to orders |
| `TICKET_REFERENCES_DOCUMENT` | 3,000 | — | 37.5% of tickets have a document reference |
| `AGENT_RESOLVED_TICKET` | 7,000 | — | 87.5% of tickets are resolved |
| `AGENT_MEMBER_OF_TEAM` | 200 | — | All agents in a team |
| `INTEGRATION_EVENT_RELATED_TO_ORDER` | 1,500 | — | |
| `INTEGRATION_EVENT_RELATED_TO_TICKET` | 500 | — | |
| `DOCUMENT_DESCRIBES_PRODUCT` | 400 | — | |

---

## 3. Seeding Strategy

### 3.1 Source Mapping

Graph nodes are derived from `curated_retail_campaign` tables. The seeding script:
1. Selects a stratified random sample of 10K customers (with proportional segment representation).
2. Follows FK relationships to populate orders, tickets, and agent assignments.
3. Generates `IntegrationEvent` and `Document` nodes from synthetic and corpus data respectively.
4. Assigns initial `cognitive_weight = 0.5` to all nodes and edges.
5. Sets `last_accessed = seeding_timestamp`.

### 3.2 Seeding Script Reference

| Script | Description | Status |
|--------|-------------|--------|
| `scripts/seed_spanner_graph.py` | Main seeding script; reads from `curated_retail_campaign`, writes to Spanner graph | To be created at E6-T3 |
| `scripts/validate_graph_seed.py` | Post-seed validation: counts, isolated nodes, edge integrity | To be created at E6-T3 |

### 3.3 Cognitive Horizon Enforcement

Per architecture mandate: traversal defaults enforce `cognitive_weight > 0.30`. Seed state sets all weights to 0.5, which clears the horizon. No nodes should be invisible immediately after seeding.

---

## 4. No-Evidence Scenario Fixtures

These fixtures represent scenarios where the graph intentionally contains **no evidence** to answer a query. They are used to validate the AMG safe-abstention behavior: the system must return a no-evidence response rather than hallucinating.

### 4.1 No-Evidence Customer Fixture

| Fixture ID | `NE-001` |
|------------|---------|
| **Fixture Type** | Missing customer |
| **Description** | A `customer_id` UUID that does not exist in the Spanner graph |
| **Fixed UUID** | `00000000-0000-0000-0000-000000000001` |
| **Expected Behavior** | Graph traversal returns empty result; AMG returns safe abstention message: "No information found for this customer in organizational memory." |
| **Benchmark Scenario** | AGENT-CC: "Show me the order history for customer 00000000-0000-0000-0000-000000000001" |
| **Validation Query** | `SELECT COUNT(*) FROM CustomerNodes WHERE customer_id = '00000000-0000-0000-0000-000000000001'` → must return 0 |

---

### 4.2 No-Evidence Product Fixture

| Fixture ID | `NE-002` |
|------------|---------|
| **Fixture Type** | Product not in graph (exists in BQ but not seeded) |
| **Description** | A `product_id` that exists in `curated_retail_campaign.products` but was deliberately excluded from graph seeding |
| **Fixed UUID** | `00000000-0000-0000-0000-000000000002` |
| **Expected Behavior** | Graph traversal: empty result. AMG abstains rather than returning unverified catalog data. |
| **Benchmark Scenario** | AGENT-EC: "What are the technical specifications for product 00000000-0000-0000-0000-000000000002?" |
| **Validation** | Product must exist in BQ `products` table but NOT in Spanner `ProductNodes` |

---

### 4.3 No-Evidence Support Ticket (No Document Reference)

| Fixture ID | `NE-003` |
|------------|---------|
| **Fixture Type** | Ticket with no grounding document |
| **Description** | A `Ticket` node in the graph with no `TICKET_REFERENCES_DOCUMENT` edge and no related policy document |
| **Fixed ticket_id** | `00000000-0000-0000-0000-000000000003` |
| **Expected Behavior** | Agent cannot cite a grounding document for this ticket. Returns "No supporting policy document found." |
| **Benchmark Scenario** | AGENT-EC: "Which policy applies to ticket 00000000-0000-0000-0000-000000000003?" |

---

### 4.4 No-Evidence Integration Event (Unlinked)

| Fixture ID | `NE-004` |
|------------|---------|
| **Fixture Type** | IntegrationEvent node with no relationships |
| **Description** | An `IntegrationEvent` node with no edges to any other entity |
| **Fixed event_id** | `00000000-0000-0000-0000-000000000004` |
| **Expected Behavior** | AGENT-SI returns "No order or ticket context found for this integration event." |
| **Benchmark Scenario** | AGENT-SI: "What order is related to integration event 00000000-0000-0000-0000-000000000004?" |

---

### 4.5 No-Evidence Team (Empty Team)

| Fixture ID | `NE-005` |
|------------|---------|
| **Fixture Type** | Team node with no agent members |
| **Description** | A `Team` node with no `AGENT_MEMBER_OF_TEAM` edges |
| **Fixed team_id** | `00000000-0000-0000-0000-000000000005` |
| **Expected Behavior** | AGENT-TA: "No agents are assigned to this team." |
| **Benchmark Scenario** | AGENT-TA: "Who are the members of team 00000000-0000-0000-0000-000000000005?" |

---

## 5. Graph Seed Validation Queries (Run at E6-T3)

```sql
-- 1. Total node counts per label
SELECT 'Customer' AS label, COUNT(*) AS cnt FROM CustomerNodes
UNION ALL SELECT 'Order', COUNT(*) FROM OrderNodes
UNION ALL SELECT 'Ticket', COUNT(*) FROM TicketNodes
UNION ALL SELECT 'Agent', COUNT(*) FROM AgentNodes
UNION ALL SELECT 'Team', COUNT(*) FROM TeamNodes
UNION ALL SELECT 'Product', COUNT(*) FROM ProductNodes
UNION ALL SELECT 'Document', COUNT(*) FROM DocumentNodes
UNION ALL SELECT 'IntegrationEvent', COUNT(*) FROM IntegrationEventNodes;

-- 2. Isolated customer check (no orders)
SELECT COUNT(*) AS isolated_customers
FROM CustomerNodes c
WHERE NOT EXISTS (
  SELECT 1 FROM GRAPH_TABLE(MemoryGraph
    MATCH (c2:Customer {customer_id: c.customer_id})-[:CUSTOMER_PLACED_ORDER]->(o:Order)
    RETURN 1
  )
);

-- 3. Isolated agent check (no team)
SELECT COUNT(*) AS isolated_agents
FROM AgentNodes a
WHERE NOT EXISTS (
  SELECT 1 FROM GRAPH_TABLE(MemoryGraph
    MATCH (a2:Agent {employee_id: a.employee_id})-[:AGENT_MEMBER_OF_TEAM]->(t:Team)
    RETURN 1
  )
);

-- 4. No-evidence fixture verification
SELECT customer_id FROM CustomerNodes WHERE customer_id = '00000000-0000-0000-0000-000000000001';
-- Expected: 0 rows

SELECT product_id FROM ProductNodes WHERE product_id = '00000000-0000-0000-0000-000000000002';
-- Expected: 0 rows

-- 5. Cognitive weight range check
SELECT COUNT(*) AS below_horizon_nodes
FROM (
  SELECT cognitive_weight FROM CustomerNodes
  UNION ALL SELECT cognitive_weight FROM OrderNodes
  UNION ALL SELECT cognitive_weight FROM TicketNodes
)
WHERE cognitive_weight <= 0.30;
-- Expected: 0 (all seeds at 0.5)
```
