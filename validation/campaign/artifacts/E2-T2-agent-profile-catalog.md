# E2-T2 — Mandatory Agent Profile Catalog

**Epic:** E2 — Security, Agent, and Integration Design Readiness
**Task:** E2-T2
**Date:** 2026-07-08
**Status:** Approved — FROZEN after Week 2 gate (changes require PVL sign-off)
**Owner:** MLE Lead

---

## Catalog Overview

| Agent ID | Name | Archetype | Scope | Status |
|----------|------|-----------|-------|--------|
| `AGENT-EC` | Employee Chatbot | Mandatory | Internal workforce support | Approved |
| `AGENT-CC` | Customer Chatbot | Mandatory | External customer-facing support | Approved |
| `AGENT-TA` | Task Assistant | Mandatory | Internal task orchestration and queue management | Approved |
| `AGENT-SI` | Slack and Google Integration Manager | Mandatory | Integration event routing and notifications | Approved |
| `AGENT-CM` | Calendar Manager | Mandatory | Scheduling and calendar event management | Approved |
| `AGENT-CA` | Code Assistant | Mandatory | Code review and repository assistance | Approved |
| `AGENT-IC` | Incident Coordinator | Optional | Cross-team incident management | Optional — not in benchmark scope |
| `AGENT-KC` | Knowledge Curator | Optional | Corpus ingestion and knowledge graph maintenance | Optional — not in benchmark scope |

---

## Memory Tier Reference

| Tier | Label | Description | Sensitivity |
|------|-------|-------------|------------|
| T1 | Context | Short-term session state; cleared after session | Low |
| T2 | Semantic | Long-term organizational knowledge graph (Spanner) | Medium–High |
| T3 | Audit | Immutable event log; append-only | High |

---

## Agent Profile: AGENT-EC — Employee Chatbot

**Purpose:** Answers internal employee queries grounded in organizational memory. Supports HR, IT, operations, and policy topics.

### Allowed Tools

| Tool | Allowed Operations | Rate Limit |
|------|--------------------|-----------|
| Memory retrieval (T2) | `GET /memory/retrieve` — read semantic nodes | 50 req/session |
| Memory write (T1) | `POST /context/write` — write session context only | 20 req/session |
| BigQuery query | `curated_retail_campaign` — read-only structured queries | 10 req/session |
| GCS corpus retrieval | Read policy and SOP documents | 10 req/session |
| Slack integration | Send messages to designated internal channels | 5 msg/session |

### Allowed Memory Tiers

| Tier | Access | Operations |
|------|--------|-----------|
| T1 (Context) | ✅ Read/Write | Full session context |
| T2 (Semantic) | ✅ Read only | Retrieve knowledge graph nodes and edges |
| T3 (Audit) | ❌ No access | Audit log read is denied |

### Allowed Data Domains

`employees`, `hr_policies`, `it_sops`, `operational_procedures`, `products` (read-only catalog)

### Denied Actions

- Write to T2 (Semantic) memory — reads only
- Access `CUSTOMER_*` data domains
- Access `order_payments`, `financial_ledger`, `refund_processing` data
- Invoke Jira, GitHub, or Calendar integrations
- Execute raw SQL or graph mutations
- Impersonate other agents or call agent APIs directly
- Access T3 (Audit) logs

### Failure Criteria

| Condition | Response |
|-----------|---------|
| Graph retrieval returns no evidence | Return safe-abstention response; do not hallucinate |
| Query exceeds 3 retries | Fail gracefully with error code `RETRIEVAL_EXHAUSTED` |
| Requested data domain is denied | Return `AUTHORIZATION_DENIED`; log to T3 |
| Session context write fails | Log warning; continue without context write |

### Escalation Path

`AGENT-EC` → Human operator (L1) → Product Validation Lead (L2)

---

## Agent Profile: AGENT-CC — Customer Chatbot

**Purpose:** Answers customer-facing queries about orders, products, returns, and support tickets. Strictly limited to customer's own data scope.

### Allowed Tools

| Tool | Allowed Operations | Rate Limit |
|------|--------------------|-----------|
| Memory retrieval (T2) | Retrieve nodes scoped to authenticated customer context | 30 req/session |
| Memory write (T1) | Write session context for authenticated customer | 20 req/session |
| BigQuery query | `curated_retail_campaign` — customer's own orders and tickets | 10 req/session |
| GCS corpus retrieval | Read public-facing product manuals and FAQs | 10 req/session |

### Allowed Memory Tiers

| Tier | Access | Operations |
|------|--------|-----------|
| T1 (Context) | ✅ Read/Write | Customer session only |
| T2 (Semantic) | ✅ Read only | Scoped to authenticated customer entity |
| T3 (Audit) | ❌ No access | |

### Allowed Data Domains

`products` (read-only catalog), `orders` (own customer only), `support_tickets` (own customer only), `return_policies`

### Denied Actions

- Access any other customer's data — strict single-customer scope enforcement required
- Access employee, HR, or internal SOP data
- Write to T2 (Semantic) memory
- Access payment card numbers or full account credentials
- Invoke GitHub, Jira, Slack, or Calendar integrations
- Issue refunds or modify order records (read-only on order data)

### Failure Criteria

| Condition | Response |
|-----------|---------|
| No evidence for customer's query | Safe abstention; suggest contacting human support |
| Cross-customer data access attempt | `ISOLATION_VIOLATION` error; immediate session termination; T3 audit log written |
| Auth token missing or invalid | `UNAUTHENTICATED`; reject request before any data access |

### Escalation Path

`AGENT-CC` → Customer support queue (L1) → Human agent (L2)

---

## Agent Profile: AGENT-TA — Task Assistant

**Purpose:** Manages internal task queues, routes work items, and tracks completion status across systems.

### Allowed Tools

| Tool | Allowed Operations | Rate Limit |
|------|--------------------|-----------|
| Memory retrieval (T2) | Read task, team, and employee relationship nodes | 50 req/session |
| Memory write (T1, T2) | Write session context; write task status updates to T2 | 30 req/session |
| Jira integration | Create issues, add comments, transition issue status | 20 req/session |
| GitHub integration | Read pull requests, create and read issues | 10 req/session |
| BigQuery query | `curated_retail_campaign` — task and queue metadata | 10 req/session |

### Allowed Memory Tiers

| Tier | Access | Operations |
|------|--------|-----------|
| T1 (Context) | ✅ Read/Write | |
| T2 (Semantic) | ✅ Read/Write | Task, team, and queue nodes only |
| T3 (Audit) | ❌ No access | |

### Allowed Data Domains

`employees`, `teams`, `task_queues`, `support_tickets`, `products` (read-only)

### Denied Actions

- Write to financial, payment, or refund data
- Access customer PII beyond support ticket context
- Delete Jira issues or GitHub repository content
- Access HR policy or performance data
- Invoke Slack or Calendar integrations (read-only via AGENT-SI if needed)

### Failure Criteria

| Condition | Response |
|-----------|---------|
| Jira/GitHub API call fails after 3 retries | Log integration failure to T3; return partial result with failure annotation |
| T2 write fails | Roll back; do not leave inconsistent state |
| Task routing has no valid assignee | Return `NO_ASSIGNEE_FOUND`; do not silently discard task |

### Escalation Path

`AGENT-TA` → Team lead (L1) → Product Validation Lead (L2)

---

## Agent Profile: AGENT-SI — Slack and Google Integration Manager

**Purpose:** Routes events from Slack and Google Calendar; dispatches notifications to designated channels.

### Allowed Tools

| Tool | Allowed Operations | Rate Limit |
|------|--------------------|-----------|
| Memory retrieval (T2) | Read channel routing config and user preference nodes | 20 req/session |
| Memory write (T1) | Session context only | 10 req/session |
| Slack integration | Post messages, read channel lists, lookup users | 30 req/session |
| Calendar integration | Read events, create/update events on managed calendars | 15 req/session |
| Audit write (T3) | Append integration dispatch event records | Unlimited (append-only) |

### Allowed Memory Tiers

| Tier | Access | Operations |
|------|--------|-----------|
| T1 (Context) | ✅ Read/Write | |
| T2 (Semantic) | ✅ Read only | Channel config and user preference nodes |
| T3 (Audit) | ✅ Append only | Write integration dispatch audit events |

### Allowed Data Domains

`integration_events`, `channel_routing_config`, `user_preferences` (notification settings only)

### Denied Actions

- Write to T2 Semantic memory
- Access customer PII, financial, or order data
- Invoke Jira or GitHub integrations
- Delete Slack messages or calendar events (create/update only)
- Read DM content — only public channel and bot-addressed messages

### Failure Criteria

| Condition | Response |
|-----------|---------|
| Slack rate limit exceeded | Backoff per Slack API guidelines; queue and retry; do not drop event |
| Calendar event conflict | Return conflict details; do not silently overwrite |
| No routing match for event type | Route to default `#campaign-alerts` channel; log unmatched event type |

### Escalation Path

`AGENT-SI` → Platform Engineer (L1) → Product Validation Lead (L2)

---

## Agent Profile: AGENT-CM — Calendar Manager

**Purpose:** Manages scheduling requests, team availability, and calendar event creation for internal workflows.

### Allowed Tools

| Tool | Allowed Operations | Rate Limit |
|------|--------------------|-----------|
| Memory retrieval (T2) | Read employee and team calendar preference nodes | 30 req/session |
| Memory write (T1) | Session context only | 20 req/session |
| Calendar integration | Read/create/update events; check free-busy | 20 req/session |
| Slack integration | Notify participants of scheduling decisions | 5 msg/session |

### Allowed Memory Tiers

| Tier | Access | Operations |
|------|--------|-----------|
| T1 (Context) | ✅ Read/Write | |
| T2 (Semantic) | ✅ Read only | Calendar preferences and team structure |
| T3 (Audit) | ❌ No access | |

### Allowed Data Domains

`employees`, `teams`, `calendar_preferences`, `meeting_templates`

### Denied Actions

- Access customer data, orders, or financial records
- Delete or cancel calendar events without confirmed human approval
- Write to T2 Semantic memory
- Invoke Jira or GitHub integrations
- Access sensitive meeting content (agenda bodies are opaque to the agent)

### Failure Criteria

| Condition | Response |
|-----------|---------|
| Calendar API unavailable | Return `CALENDAR_UNAVAILABLE`; do not proceed with scheduling |
| Conflicting attendee constraint | Surface conflict to requestor; do not auto-resolve by dropping attendees |
| Free-busy data incomplete | Treat as conflict; request human confirmation |

### Escalation Path

`AGENT-CM` → Meeting organizer (L1) → Human operator (L2)

---

## Agent Profile: AGENT-CA — Code Assistant

**Purpose:** Supports code review, PR summarization, and issue management within authorized repositories.

### Allowed Tools

| Tool | Allowed Operations | Rate Limit |
|------|--------------------|-----------|
| Memory retrieval (T2) | Read repository and code context nodes | 40 req/session |
| Memory write (T1, T2) | Write session context; write code-context nodes to T2 | 20 req/session |
| GitHub integration | Read repos, issues, PRs; create and reply to issue comments | 20 req/session |
| BigQuery query | `benchmark_metrics` — read-only, for code metric queries | 5 req/session |

### Allowed Memory Tiers

| Tier | Access | Operations |
|------|--------|-----------|
| T1 (Context) | ✅ Read/Write | |
| T2 (Semantic) | ✅ Read/Write | Code context and repository relationship nodes |
| T3 (Audit) | ❌ No access | |

### Allowed Data Domains

`repositories`, `pull_requests`, `issues`, `code_metrics`

### Denied Actions

- Push code, create branches, or merge pull requests
- Delete issues, comments, or repository content
- Access customer PII, financial, or order data
- Invoke Slack, Calendar, or Jira integrations directly
- Access secrets, credentials, or environment configuration files in repositories

### Failure Criteria

| Condition | Response |
|-----------|---------|
| Repository not in allowed list | `REPOSITORY_NOT_AUTHORIZED`; do not proceed |
| PR diff exceeds token context window | Summarize partial diff and annotate as `TRUNCATED` |
| Attempted push or branch creation | `WRITE_OPERATION_DENIED`; log to T3; terminate action |

### Escalation Path

`AGENT-CA` → Engineer owner of repository (L1) → MLE Lead (L2)

---

## Optional Agents (Out of Benchmark Scope)

### AGENT-IC — Incident Coordinator (Optional)
- Not included in mandatory benchmark scenarios
- Profile to be defined if budget allows extended scope (E7-T6)

### AGENT-KC — Knowledge Curator (Optional)
- Not included in mandatory benchmark scenarios
- Profile to be defined if budget allows extended scope (E7-T6)

---

## Profile Freeze Rules

1. This catalog is frozen after Week 2 gate sign-off.
2. Changes to allowed tools, memory tiers, or denied actions require PVL written approval and a catalog version increment.
3. Agent IDs (`AGENT-EC`, etc.) are immutable — they appear in benchmark run manifests and audit logs.
4. Any agent profile change after Week 4 infrastructure gate is prohibited without a benchmark re-run.
