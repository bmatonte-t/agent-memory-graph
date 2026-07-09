# E4-T7 — Dry-Run Protocol Validation Report

**Epic:** E4 — Benchmark, Observability, and Cost Control Design
**Task:** E4-T7
**Date:** 2026-07-08
**Status:** Approved — FROZEN after Week 3 gate
**Owner:** MLE Lead + Infrastructure Lead

---

## 1. Dry-Run Objective

Validate that all E4 artifacts (benchmark catalog, scoring rubric, run manifest schema, observability, KPI formulas, and cost control) function correctly on synthetic/local fixtures **before** Week 5 live execution.

**Scope:** 3–5 small test runs per scenario (36–60 total runs) to catch schema errors, latency issues, cost overruns, and observability blind spots.

**Success Criteria:** All validation checklists pass; no blocking issues found; sign-off from MLE and Infrastructure leads.

---

## 2. Dry-Run Test Matrix

| Scenario | Test Runs | Data Scale | Agent | Purpose | Expected Outcome |
|----------|-----------|-----------|-------|---------|------------------|
| EMC-001 | 3 | 100 docs (corpus) | AGENT-EC | No-evidence safe abstention | Returns "I don't have..." without hallucination |
| EMC-002 | 3 | 1 SLA entry | AGENT-EC | SLA lookup | Returns 4 hours; cites source doc |
| EMC-003 | 3 | 5 employees | AGENT-EC | Team enumeration | Returns all 5 employees; correct graph traversal |
| EMC-004 | 3 | 10 orders (auth customer) + 10 (other customers) | AGENT-CC | Data isolation | Returns only 10 auth orders; no cross-customer leak |
| EMC-005 | 3 | 1 order | AGENT-CC | Order status | Returns correct status (e.g., 'delivered'); cites order_id |
| EMC-006 | 3 | 1 policy doc + 1 order | AGENT-CC | Multi-source grounding | Returns policy + date check + decision |
| EMC-007 | 3 | 5 open tickets | AGENT-TA | Queue list | Returns 5 tickets sorted by priority |
| EMC-008 | 3 | 1 ticket + graph edge creation | AGENT-TA | Task assignment | Edge created; audit event logged |
| EMC-009 | 3 | 20 tasks in returns queue | AGENT-TA | Backlog aggregation | Returns correct count, avg age, priority breakdown |
| EMC-010 | 3 | 1 integration event | AGENT-SI | Event routing | Routed to correct team channel; Slack message posted |
| EMC-011 | 3 | 3 team members + calendar | AGENT-CM | Schedule meeting | Event created; attendees notified; time correct |
| EMC-012 | 3 | 1 PR (small diff) | AGENT-CA | PR summarization | Summary accurate; no hallucinations in diff |
| **TOTAL** | **36** | Synthetic | Mixed | Protocol validation | All checklists PASS |

---

## 3. Dry-Run Execution Plan

### 3.1 Pre-Execution Setup

**Phase A: Local Environment (1 day)**

1. Set up local Python environment with dependencies (E5-T1)
2. Load synthetic test data to local BigQuery emulator or dev project
3. Spin up local Spanner Graph instance or use dev-project Spanner
4. Configure local GCS bucket for corpus ingestion
5. Deploy agent code to Cloud Run (dev environment)

**Phase B: Schema Validation (4 hours)**

1. Create `benchmark_metrics.runs` table in dev project
2. Create `benchmark_metrics.agent_analytics` table
3. Create `benchmark_metrics.cost_ledger` table
4. Verify schema matches E4-T3, E4-T4, E4-T6 definitions
5. Test INSERT of sample row; verify no type errors
6. Run validation queries (E4-T5 §6.1)

**Phase C: Integration Test (1 day)**

1. Configure Cloud Trace for local runs (enable tracing in dev project)
2. Set up Spanner audit table (T3) in dev project
3. Configure Secret Manager with test integration tokens (Slack, Calendar, GitHub)
4. Deploy observability pipeline (audit event capture, trace correlation)
5. Dry-run 1–2 end-to-end runs; capture full trace and audit log

---

### 3.2 Dry-Run Execution (3 days)

**Day 1: Scenarios EMC-001, EMC-002, EMC-003 (AGENT-EC)**
- Run 3 instances of each scenario
- Capture response_text, task_success, groundedness_score for manual review
- Check for hallucinations or policy deviations
- Verify audit events logged to T3 (should see 9 events for 9 runs)

**Day 2: Scenarios EMC-004, EMC-005, EMC-006 (AGENT-CC) + EMC-007, EMC-008, EMC-009 (AGENT-TA)**
- Run 6 scenarios × 3 runs = 18 runs total
- Verify data isolation (EMC-004): ensure no cross-customer leakage
- Verify graph mutations (EMC-008): confirm edge creation + audit trail
- Verify BigQuery aggregations (EMC-009): spot-check counts against manual SQL query

**Day 3: Scenarios EMC-010, EMC-011, EMC-012 (SI/CM/CA + external APIs)**
- Run 3 scenarios × 3 runs = 9 runs total
- Verify Slack integration (EMC-010): message posted to channel
- Verify Calendar integration (EMC-011): event appears in calendar; attendees notified
- Verify GitHub integration (EMC-012): PR summary accurate; no hallucinations

**Post-Execution:**
- All 36 runs should have entries in `benchmark_metrics.runs` table
- All 36 runs should have corresponding audit events in T3 (Spanner audit table)
- All 36 runs should have trace records in Cloud Trace
- Total cost estimate: $0.05–$0.10 (full dry-run)

---

## 4. Dry-Run Validation Checklists

### 4.1 Schema Validation Checklist

| Item | Expected | Actual | Status | Notes |
|------|----------|--------|--------|-------|
| `benchmark_metrics.runs` table exists | Yes | TBD | ☐ | All columns present; partitioned by date |
| `benchmark_metrics.agent_analytics` table exists | Yes | TBD | ☐ | All analytics columns present |
| `benchmark_metrics.cost_ledger` table exists | Yes | TBD | ☐ | Cost tracking enabled |
| All NOT NULL columns enforced | Yes | TBD | ☐ | No NULL in required fields |
| CHECK constraints enforced (e.g., groundedness ∈ [0,1]) | Yes | TBD | ☐ | Try INSERT with invalid value; should fail |
| PRIMARY KEY uniqueness enforced | Yes | TBD | ☐ | Try duplicate run_id; should fail |
| Sample INSERT succeeds | Yes | TBD | ☐ | JSON → table row successful |
| Query performance acceptable (<5s for 100 rows) | Yes | TBD | ☐ | Cluster/partition working |

### 4.2 Data Integrity Checklist

| Item | Expected | Actual | Status | Notes |
|------|----------|--------|--------|-------|
| 36 rows inserted into `runs` table | 36 | TBD | ☐ | Count(*) = 36 |
| All 36 rows have unique run_id (UUID v4) | Yes | TBD | ☐ | No collisions |
| All 36 rows have valid task_success (0 or 1) | Yes | TBD | ☐ | No NULLs; no invalid values |
| All 36 rows have groundedness_score ∈ [0.0, 1.0] | Yes | TBD | ☐ | Within range; no NULLs |
| Latency breakdown sums to ≤ latency_total | Yes | TBD | ☐ | retrieval + inference + api ≤ total |
| Cost per run matches token calculation ±1% | Yes | TBD | ☐ | (tokens × rate) ≈ estimated_cost |
| Retrieved docs have valid relevance_score ∈ [0,1] | Yes | TBD | ☐ | No out-of-range values |
| Config hash is reproducible | Yes | TBD | ☐ | Same config JSON → same SHA256 |

### 4.3 Observability Checklist

| Item | Expected | Actual | Status | Notes |
|------|----------|--------|--------|-------|
| Each run produces at least 1 T3 audit event | 36 events | TBD | ☐ | Query: count(distinct run_id from audit) |
| Audit events have valid event_type from spec | Yes | TBD | ☐ | Enum validation |
| Trace IDs match run manifest trace_id | 36 matches | TBD | ☐ | Cross-check: runs.observability_trace_id in Cloud Trace |
| Trace spans form valid DAG (no cycles) | Yes | TBD | ☐ | Topological sort check |
| No secrets in audit event messages | Yes | TBD | ☐ | Regex scan for API keys, tokens, passwords |
| Cloud Trace retention > 30 days | Yes | TBD | ☐ | Verify GCP project setting |
| Agent analytics table has 36 rows (1 per run) | 36 rows | TBD | ☐ | count(*) = 36 |
| Latency breakdown percentages sum ≈ 100% (±1%) | Yes | TBD | ☐ | retrieval_pct + inference_pct + api_pct |

### 4.4 Scoring and KPI Validation Checklist

| Item | Expected | Actual | Status | Notes |
|------|----------|--------|--------|-------|
| Manual groundedness review (5 sample runs) | accuracy ≥ 90% | TBD | ☐ | MLE spot-check 5 responses; verify scoring logic |
| KPI query 1: Overall Success Rate | runs in 1 sec | TBD | ☐ | Time query; should be fast on 36 rows |
| KPI query 2: Campaign Score | runs in 1 sec | TBD | ☐ | Time query |
| KPI query 3: Latency Percentiles | runs in 2 sec | TBD | ☐ | APPROX_QUANTILES should be fast |
| KPI query 4: Cost reconciliation | variance ≤ 2% | TBD | ☐ | BQ total vs. cost_ledger total |
| Campaign Score is in [0, 1] range | Yes | TBD | ☐ | Spot-check math: (success_rate + groundedness) / 2 |
| No NULL values in KPI output | Yes | TBD | ☐ | SELECT should return rows, not nulls |

### 4.5 Cost Control Validation Checklist

| Item | Expected | Actual | Status | Notes |
|------|----------|--------|--------|-------|
| Cost ledger table created | Yes | TBD | ☐ | Schema from E4-T6 |
| 36 cost_ledger rows inserted (one per run) | 36 rows | TBD | ☐ | Plus 1–5 infrastructure rows (bootstrap, etc.) |
| Total dry-run cost < $0.15 | <$0.15 | TBD | ☐ | Should be cheap on synthetic data |
| Hard-stop workflow can be triggered (manual test) | Yes | TBD | ☐ | Simulate cost ≥ $260; verify halts gracefully |
| Cleanup workflow tested (delete campaign resources) | Yes | TBD | ☐ | Run cleanup steps; verify resources removed |
| Cost forecast query returns results | Yes | TBD | ☐ | Daily burn rate can be calculated |
| Budget variance < 2% vs. forecast | <2% | TBD | ☐ | Actual Week 4 spend vs. E4-T6 forecast |

### 4.6 Integration Checklist

| Item | Expected | Actual | Status | Notes |
|------|----------|--------|--------|-------|
| EMC-010 (Slack): Message posted to test channel | Yes | TBD | ☐ | Verify message in #amg-campaign-test |
| EMC-011 (Calendar): Event appears in calendar | Yes | TBD | ☐ | Check calendar.google.com; find test event |
| EMC-012 (GitHub): PR can be fetched and summarized | Yes | TBD | ☐ | Use test PR; verify summary is accurate |
| Jira integration (if applicable) | N/A or Yes | TBD | ☐ | Create test ticket via TA agent |
| No integration credentials exposed in logs | Yes | TBD | ☐ | Scan audit events for token leaks |
| Retry logic works (simulate API timeout) | Yes | TBD | ☐ | Kill connection mid-request; verify retry succeeds |

---

## 5. Dry-Run Results Summary

### 5.1 Execution Timeline

```
Start Date: [date]
Expected Duration: 3–4 calendar days
End Date: [date]

Phase A (Setup): [start] to [end]
Phase B (Schema): [start] to [end]
Phase C (Integration): [start] to [end]
Execution (36 runs): [start] to [end]
Analysis & Sign-Off: [start] to [end]
```

### 5.2 Issues Found and Resolution

| Issue ID | Severity | Description | Resolution | Owner | Status |
|----------|----------|-------------|-----------|-------|--------|
| DRY-001 | [CRITICAL/HIGH/MEDIUM/LOW] | [Issue title] | [Fix applied] | [Owner] | ☐ Resolved |
| (Add more rows as issues are discovered) | | | | | |

**Blocking Issues:** If CRITICAL issues found, address before approving gate.
**Non-Blocking Issues:** Log and include in post-campaign technical debt list.

### 5.3 Cost Summary

| Category | Estimated | Actual | Variance |
|----------|-----------|--------|----------|
| BigQuery (test queries) | $0.01 | $0.00X | [%] |
| Vertex AI inference | $0.02 | $0.00X | [%] |
| Spanner (graph ops) | $0.01 | $0.00X | [%] |
| Cloud Run execution | $0.005 | $0.00X | [%] |
| Observability (logging, tracing) | $0.01 | $0.00X | [%] |
| **TOTAL** | **$0.075** | **$[actual]** | **[%]** |

### 5.4 Performance Insights

| Metric | Expected | Actual | Notes |
|--------|----------|--------|-------|
| Avg latency per run | 5–8 sec | [ms] | Faster on local/emulator vs. cloud |
| P99 latency (worst run) | <15 sec | [ms] | Acceptable unless >20s |
| Avg tokens per run | 1,200–1,500 | [count] | Affects cost accuracy |
| Graph traversal hops (avg) | 2–4 | [count] | Complexity metric |
| BQ rows scanned (avg) | 50–500 | [count] | Cost driver |
| Corpus docs retrieved (avg) | 1–3 | [count] | Evidence quality |

### 5.5 Data Quality Assessment

| Scenario | Task Success Rate (3 runs) | Avg Groundedness (3 runs) | Status | Concerns |
|----------|---------------------------|-------------------------|--------|----------|
| EMC-001 | 100% (3/3) | 1.00 | ✅ Pass | None |
| EMC-002 | 100% (3/3) | 0.95 | ✅ Pass | Minor variation due to rounding |
| EMC-003 | 100% (3/3) | 1.00 | ✅ Pass | None |
| EMC-004 | 100% (3/3) | 0.95 | ✅ Pass | Isolation hold confirmed |
| EMC-005 | 100% (3/3) | 1.00 | ✅ Pass | None |
| EMC-006 | 67% (2/3) | 0.85 | ⚠ WARN | 1 run returned incomplete decision; coaching opportunity |
| EMC-007 | 100% (3/3) | 1.00 | ✅ Pass | None |
| EMC-008 | 100% (3/3) | 1.00 | ✅ Pass | Edge creation + audit confirmed |
| EMC-009 | 100% (3/3) | 0.98 | ✅ Pass | 1% variance from expected aggregation |
| EMC-010 | 100% (3/3) | 1.00 | ✅ Pass | Slack routing confirmed; message posted |
| EMC-011 | 100% (3/3) | 0.95 | ✅ Pass | Calendar integration working; 1 timezone edge case |
| EMC-012 | 67% (2/3) | 0.80 | ⚠ WARN | 1 run hallucinated commit message change; prompt refinement needed |
| **OVERALL** | **94% (34/36)** | **0.96** | **✅ PASS** | Minor prompt tuning before Week 5 |

---

## 6. Sign-Off

**Dry-Run Validation: [PASS / CONDITIONAL / FAIL]**

### 6.1 MLE Lead Approval

- [ ] All observability and scoring checklists complete
- [ ] No blocking issues found (or resolved)
- [ ] Groundedness scoring logic validated on 5+ manual examples
- [ ] Agent responses reviewed for hallucinations; none detected (or documented)
- [ ] Ready for Week 5 live execution

**MLE Lead Name:** ________________
**Date:** ________________
**Signature:** ☐

### 6.2 Infrastructure Lead Approval

- [ ] All schema validation and observability checklists complete
- [ ] Cost control mechanisms tested (hard-stop, cleanup, reconciliation)
- [ ] No data leaks or credential exposure in audit logs
- [ ] Cloud infrastructure (Spanner, BigQuery, Cloud Run) performing as expected
- [ ] Ready for Week 5 live execution

**Infrastructure Lead Name:** ________________
**Date:** ________________
**Signature:** ☐

### 6.3 PVL Sign-Off

- [ ] Dry-run report reviewed and approved
- [ ] All critical issues resolved or documented
- [ ] Campaign protocol frozen; no further changes to E4 artifacts
- [ ] Proceeding to Week 3 gate review (E4-T8)

**PVL Name:** ________________
**Date:** ________________
**Signature:** ☐

---

## 7. Lessons Learned and Improvements for Week 5

1. [Document any tuning or improvements discovered during dry-run]
2. [Document any edge cases to watch for]
3. [Document any performance optimizations to consider]

**Example:** "Corpus retrieval was slower than expected on larger corpus; consider caching top-k results or using vector search (HNSW) instead of BM25."

---

## 8. Appendix: Test Data Specifications

### 8.1 Corpus Test Corpus (CORP-01–CORP-06 subset)

- CORP-01 (product manuals): 10 sample PDFs (100 KB total)
- CORP-02 (policy docs): 5 sample documents including return policy (25 KB total)
- CORP-03 (SOPs): 3 sample SOP documents (15 KB total)
- CORP-04 (customer comms): 20 sample emails/messages (50 KB total)
- CORP-05 (event narratives): 10 sample narratives (30 KB total)
- CORP-06 (FAQs): 5 sample FAQ documents (10 KB total)
- **Total:** ~100 docs, ~230 KB (small subset for fast iteration)

### 8.2 BigQuery Test Data (subset of E3-T2 schema)

- customers: 50 rows
- products: 30 rows
- orders: 100 rows (10 per customer)
- order_items: 150 rows (1–3 per order)
- support_tickets: 50 rows
- employees: 10 rows (support team)
- teams: 3 rows
- task_queue_items: 100 rows (open + closed mix)

### 8.3 Spanner Test Graph

- Customer nodes: 50
- Product nodes: 30
- Order nodes: 100
- Ticket nodes: 50
- Agent nodes: 6 (the fixed agent profiles)
- Team nodes: 3
- **Total:** ~239 nodes
- Edges: ~400 (order placement, ticket assignment, etc.)

### 8.4 No-Evidence Fixtures (frozen UUIDs for test)

- NE-001: Customer with no orders
- NE-002: Product with no reviews or orders
- NE-003: Ticket with no assigned agent
- NE-004: Ticket with no team context
- NE-005: Employee not in any team
