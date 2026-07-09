# E4-T1 — Benchmark Scenario Catalog

**Epic:** E4 — Benchmark, Observability, and Cost Control Design
**Task:** E4-T1
**Date:** 2026-07-08
**Status:** Approved — FROZEN after Week 3 gate
**Owner:** MLE Lead

---

## 1. Benchmark Scope

**All scenarios are grounded in E2-T2 mandatory agent profiles and E3-T1 canonical data schema.**

No new agents or data domains may be added to scenarios after this gate without explicit PVL approval and budget re-review.

---

## 2. Mandatory Scenario Matrix

| Scenario ID | Agent | Task | Data Domain | Baseline (Comparison) | Min Runs | Notes |
|------------|-------|------|------------|--------|----------|-------|
| EMC-001 | AGENT-EC | "Retrieve our return policy" | policy_docs | BQ direct query | 30 | No-evidence safe abstention test |
| EMC-002 | AGENT-EC | "What's the SLA for urgent tickets?" | sop_docs | BQ direct query | 30 | Knowledge graph traversal |
| EMC-003 | AGENT-EC | "List active employees in support" | employees/teams | BQ direct query | 30 | Graph relationship recall |
| EMC-004 | AGENT-CC | "Show me my order history" | orders/order_items | BQ direct query (scoped) | 30 | Customer data isolation |
| EMC-005 | AGENT-CC | "What's the status of order ABC?" | orders | BQ direct query | 30 | Order lookup accuracy |
| EMC-006 | AGENT-CC | "Can I return this product?" | refunds/return_policy | corpus + BQ | 30 | Multi-source grounding |
| EMC-007 | AGENT-TA | "List open support tickets" | support_tickets | BQ query + direct API | 30 | Filter/sort correctness |
| EMC-008 | AGENT-TA | "Assign ticket XYZ to employee ABC" | task_queue_items | Graph mutation + audit | 30 | Task orchestration |
| EMC-009 | AGENT-TA | "What's the backlog for returns queue?" | task_queue_items/refunds | BQ aggregation | 30 | Queue status accuracy |
| EMC-010 | AGENT-SI | "Route Slack event to correct team" | integration_events + teams | Graph routing rule | 30 | Event routing correctness |
| EMC-011 | AGENT-CM | "Schedule a team sync for tomorrow" | calendar + employees | Calendar API + graph | 30 | Calendar availability check |
| EMC-012 | AGENT-CA | "Summarize this PR for the team" | github_pr_content | GitHub API + corpus | 30 | Code context extraction |

**Total minimum runs:** 12 scenarios × 30 runs = **360 measured runs**

---

## 3. Scenario Specifications

### EMC-001 — Employee Return Policy Lookup (No-Evidence Safe Abstention)

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-001` |
| **Agent** | AGENT-EC |
| **Agent Profile** | Employee Chatbot (from E2-T2) |
| **Task** | Retrieve and describe the organization's return policy |
| **User Query** | "Retrieve our return policy" |
| **Data Source** | `policy_docs` corpus (CORP-02 from E3-T3) |
| **Primary Success Criterion** | Agent returns policy document content grounded in corpus; cites `DOCUMENT_ID` |
| **No-Evidence Path** | If corpus has no return policy (synthetic gap), agent returns safe abstention: "I don't have a return policy document in my knowledge base" |
| **Failure Modes** | Hallucinated policy details; returned policy from different organization; no citation |
| **Max Latency** | 10 seconds |
| **Seed Dataset** | CORP-02 (40 policy docs); 5% seed gap (no return policy) |
| **Baseline** | Direct BigQuery query to `policy_docs` table (BQ latency + retrieval) |

---

### EMC-002 — SLA Configuration and Ticket Escalation

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-002` |
| **Agent** | AGENT-EC |
| **Task** | Answer question about SLA response time for urgent priority tickets |
| **User Query** | "What's the SLA for urgent tickets?" |
| **Data Source** | `sop_docs` corpus + Spanner graph (`sla_config` node edges) |
| **Primary Success Criterion** | Agent retrieves `sla_config` response_sla_hours for priority='urgent' and cites source document |
| **Pass Threshold** | Correct SLA value AND document citation |
| **Failure Modes** | Wrong SLA value; no citation; generic response without grounding |
| **Max Latency** | 8 seconds |
| **Baseline** | Direct BQ query to `curated_retail_campaign.sla_config` |

---

### EMC-003 — Team Member Enumeration

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-003` |
| **Agent** | AGENT-EC |
| **Task** | List all active support team members |
| **User Query** | "List active employees in support" |
| **Data Source** | Spanner graph: `AGENT` -[:AGENT_MEMBER_OF_TEAM]-> `TEAM` (filtered by department='support') |
| **Primary Success Criterion** | Returns all employees with `department='support'` and `is_active=true` |
| **Graph Traversal** | Must use `AGENT_MEMBER_OF_TEAM` relationship + filter |
| **Pass Threshold** | ≥95% precision, ≥95% recall |
| **Max Latency** | 5 seconds |
| **Baseline** | BQ query: `SELECT * FROM curated_retail_campaign.employees WHERE department='support' AND is_active=true` |

---

### EMC-004 — Customer Order History (Isolation Test)

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-004` |
| **Agent** | AGENT-CC |
| **Task** | Retrieve authenticated customer's order history |
| **User Query** | "Show me my order history" |
| **Auth Context** | Customer ID provided in session (e.g., `cust-12345`) |
| **Data Source** | Spanner graph + BQ: `CUSTOMER` -[:CUSTOMER_PLACED_ORDER]-> `ORDER` |
| **Primary Success Criterion** | Returns only orders belonging to authenticated customer; no other customer data visible |
| **Isolation Test** | Verify cross-customer data isolation enforced (from E2-T5 smoke plan SEC-A-01) |
| **Failure Modes** | Orders from other customers returned; unbounded query result |
| **Max Latency** | 6 seconds |
| **Baseline** | BQ query scoped to `customer_id = :authenticated_id` |

---

### EMC-005 — Order Status Lookup

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-005` |
| **Agent** | AGENT-CC |
| **Task** | Retrieve status of a specific order |
| **User Query** | "What's the status of order ABC?" (where ABC is a valid order_id from seed) |
| **Data Source** | Spanner: `ORDER` node + BQ: `orders` table |
| **Primary Success Criterion** | Returns correct order status (e.g., 'delivered', 'pending') with timestamp |
| **Accuracy Threshold** | 100% (exact status match) |
| **Max Latency** | 4 seconds |
| **Baseline** | BQ query to `orders` table with `order_id = :order_id` |

---

### EMC-006 — Return Eligibility with Multi-Source Grounding

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-006` |
| **Agent** | AGENT-CC |
| **Task** | Determine if a customer can return a product |
| **User Query** | "Can I return this product?" (customer has a specific order and product) |
| **Data Source** | Return policy corpus (CORP-02) + `refunds` schema + `orders` + `products` |
| **Primary Success Criterion** | Agent cites return policy AND checks order eligibility (date, product type, customer consent) |
| **Complex Grounding** | Must synthesize corpus policy + structured data + business rules |
| **Max Latency** | 12 seconds |
| **Baseline** | Multi-query BQ workflow: (1) fetch return policy metadata, (2) check order date, (3) validate product |

---

### EMC-007 — Support Queue List

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-007` |
| **Agent** | AGENT-TA |
| **Task** | List all open support tickets in a queue |
| **User Query** | "List open support tickets" |
| **Data Source** | Spanner: `TICKET` -[:CUSTOMER_OPENED_TICKET]-> `CUSTOMER` + BQ: `support_tickets` |
| **Filter** | `status IN ('open', 'in_progress')` |
| **Primary Success Criterion** | Returns all matching tickets sorted by priority (high → low) |
| **Sort Correctness** | Verify correct priority ordering per SLA config |
| **Max Latency** | 7 seconds |
| **Baseline** | BQ query with `WHERE status IN (...)` and `ORDER BY priority_numeric` |

---

### EMC-008 — Task Assignment and Audit

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-008` |
| **Agent** | AGENT-TA |
| **Task** | Assign a ticket to an employee |
| **User Query** | "Assign ticket XYZ to employee ABC" |
| **Data Source** | Spanner graph mutation: create `AGENT_RESOLVED_TICKET` edge; append to T3 audit log |
| **Precondition** | Ticket `XYZ` exists unassigned; employee `ABC` is active |
| **Primary Success Criterion** | Edge created in Spanner; audit event written to T3 with timestamp |
| **Atomicity** | Edge creation and audit write must be transactional |
| **Max Latency** | 8 seconds |
| **Baseline** | Two-step manual process: (1) update `task_queue_items`, (2) write audit log |

---

### EMC-009 — Backlog Aggregation

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-009` |
| **Agent** | AGENT-TA |
| **Task** | Report backlog statistics for returns processing queue |
| **User Query** | "What's the backlog for returns queue?" |
| **Data Source** | BQ: `task_queue_items` aggregation (queue='returns_processing') |
| **Metrics** | Total open tasks, avg time in queue, count by priority, oldest task age |
| **Primary Success Criterion** | Returns accurate aggregation with correct counts and timestamps |
| **Correctness** | Verify against baseline SQL `COUNT()`, `AVG(TIMESTAMP_DIFF(...))`, `GROUP BY` |
| **Max Latency** | 9 seconds |
| **Baseline** | BQ aggregation query with GROUP BY and window functions |

---

### EMC-010 — Integration Event Routing

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-010` |
| **Agent** | AGENT-SI |
| **Task** | Route incoming Slack event to correct team |
| **User Query** | Event payload: `{type: 'support_ticket', team: 'tier1', urgency: 'high'}` |
| **Data Source** | Spanner: `INTEGRATION_EVENT` -[:INTEGRATION_EVENT_RELATED_TO_TICKET]-> `TICKET` -[:CUSTOMER_OPENED_TICKET]-> `CUSTOMER`, lookup `TEAM` |
| **Routing Rule** | Route to team that owns the ticket category |
| **Primary Success Criterion** | Event routed to correct `#channel` (Slack) with no message loss or duplication |
| **Audit** | T3 event log records routing decision |
| **Max Latency** | 6 seconds |
| **Baseline** | Hardcoded routing table lookup |

---

### EMC-011 — Calendar Event Scheduling

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-011` |
| **Agent** | AGENT-CM |
| **Task** | Schedule a team sync meeting |
| **User Query** | "Schedule a team sync for tomorrow" |
| **Data Source** | Spanner: `TEAM` -[AGENT_MEMBER_OF_TEAM]-> `AGENT`; Calendar API; free-busy data |
| **Constraint** | Find a 1-hour slot when all team members are free |
| **Primary Success Criterion** | Event created on `AMG Campaign Scheduling` calendar; all participants notified; event at correct time |
| **Failure Modes** | Conflict not detected; scheduled over existing meeting; sent to wrong calendar |
| **Max Latency** | 15 seconds (includes Calendar API call) |
| **Baseline** | Manual free-busy check + manual event creation |

---

### EMC-012 — Pull Request Summarization

| Field | Value |
|-------|-------|
| **Scenario ID** | `EMC-012` |
| **Agent** | AGENT-CA |
| **Task** | Summarize a GitHub PR for team discussion |
| **User Query** | "Summarize this PR for the team" (PR URL or ID provided) |
| **Data Source** | GitHub API (PR diff, comments, linked issues) + corpus code examples |
| **Primary Success Criterion** | Summary is concise (<200 words), accurate, and highlights key changes, approvals, and risks |
| **Accuracy** | No hallucinated changes; all cited changes present in diff |
| **Max Latency** | 20 seconds (includes GitHub API + LLM processing) |
| **Baseline** | GitHub web interface PR summary (human-readable) |

---

## 4. No-Evidence Scenarios

In addition to isolated entity no-evidence fixtures (E3-T4), scenarios must test no-evidence **query paths**:

| Scenario | No-Evidence Trigger | Expected Response |
|----------|-------------------|------------------|
| EMC-001 | Corpus has no return policy (CORP-02 gap at seed time) | "I don't have a return policy document in my knowledge base." |
| EMC-002 | Ticket priority value not in `sla_config` | "No SLA defined for this priority level." |
| EMC-003 | Support department has no team members | "No active employees found in support department." |
| EMC-004 | Customer has no orders | "You have no order history." |
| EMC-010 | Ticket is not linked to any team (NE-004 fixture) | "No team context found for this event." |

**All no-evidence responses must avoid hallucination. If confidence < 0.30 (cognitive horizon), return abstention.**

---

## 5. Scenario Freeze and Version Pinning

Effective after Week 3 gate:

- Scenario IDs `EMC-001` through `EMC-012` are immutable
- Agent, task, and success criteria are frozen — no mid-benchmark changes
- Run manifests reference scenario_id + version `v1.0`
- Any bug fix or clarification after start of Week 5 execution requires a version bump (v1.1) and separate benchmark track

---

## 6. Scenario Readiness Checklist (Verified at E4-T7)

| Scenario | Seeds Prepared | Baseline Query Ready | Expected Output Known | Notes |
|----------|--------------|-------------------|---------------------|-------|
| EMC-001 | ☐ | ☐ | ☐ | No-evidence path validated |
| EMC-002 | ☐ | ☐ | ☐ | |
| EMC-003 | ☐ | ☐ | ☐ | Graph path validated |
| EMC-004 | ☐ | ☐ | ☐ | Isolation test confirmed |
| EMC-005 | ☐ | ☐ | ☐ | |
| EMC-006 | ☐ | ☐ | ☐ | Multi-source grounding validated |
| EMC-007 | ☐ | ☐ | ☐ | |
| EMC-008 | ☐ | ☐ | ☐ | Audit write confirmed |
| EMC-009 | ☐ | ☐ | ☐ | |
| EMC-010 | ☐ | ☐ | ☐ | Routing logic validated |
| EMC-011 | ☐ | ☐ | ☐ | Calendar integration dry-run |
| EMC-012 | ☐ | ☐ | ☐ | GitHub integration dry-run |
