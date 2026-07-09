# E7-prep-T7: Failure Taxonomy and Rerun Eligibility Rules
# Grounded in E4-T5 (KPI definitions), E6-T6 (smoke test failures), E4-T2 (scenario rubric)
# Status: FROZEN — Use during E7-exec-T6 to classify failures; E7-exec-T7 for rerun decisions

---

## Taxonomy Overview

Failures are classified into four top-level domains:
1. **Agent Failures** (AF) — Failures in the agent's reasoning or retrieval pipeline
2. **Integration Failures** (IF) — Failures in external API calls (Slack, Jira, GitHub, Calendar)
3. **Infrastructure Failures** (INF) — Failures in GCP services (Spanner, BigQuery, Cloud Run)
4. **Systemic Failures** (SYS) — Campaign-level conditions (budget, TTL)

Each category specifies:
- **Root cause**: What caused the failure
- **Transient?**: Can a simple retry fix it?
- **Rerun eligible**: Whether a new run is permitted
- **Max reruns**: Upper bound on retries (never infinite)
- **Delay before rerun**: Wait period to allow transient conditions to clear
- **Escalation**: Who to notify beyond automated retry

---

## Domain AF: Agent Failures

### AF-001: Retrieval Timeout
- **Description**: Agent's graph/corpus retrieval stage exceeded the scenario max latency without returning evidence.
- **Indicators**: `outcome=timeout`, `retrieval_latency_ms > 5000`, `nodes_traversed=0`
- **Root cause**: Spanner graph query timeout; network latency spike; query plan regression
- **Transient?**: Yes — typically resolves within 5–30 seconds
- **Rerun eligible**: Yes
- **Max reruns**: 2
- **Delay before rerun**: 10,000ms
- **Escalation**: None if ≤2 occurrences per scenario per hour; Infrastructure Lead if >5/hour

### AF-002: Inference Error (Gemini API Error)
- **Description**: Vertex AI / Gemini returned a non-200 status or malformed response.
- **Indicators**: `outcome=error`, `error_type=VertexAIError OR APIError`, `tokens_total=0`
- **Root cause**: Vertex AI rate limit; malformed prompt; model availability issue
- **Transient?**: Sometimes — rate limits clear; prompt format issues do not
- **Rerun eligible**: Yes, for rate-limit errors only (`error_message contains "429" OR "quota"`)
- **Max reruns**: 1
- **Delay before rerun**: 30,000ms (Gemini rate limit recovery)
- **Escalation**: Infrastructure Lead if >3 occurrences per scenario

### AF-003: Task Failure (Grounding Below Threshold)
- **Description**: Agent returned a response, but groundedness_score < 0.50. Task not successful per E4-T2 rubric.
- **Indicators**: `task_success=false`, `groundedness_score < 0.50`, `outcome=task_failure`
- **Root cause**: Corpus miss; incorrect graph traversal; hallucination
- **Transient?**: No — same query will likely produce same result
- **Rerun eligible**: No (systematic issue; rerunning doesn't improve groundedness)
- **Max reruns**: 0
- **Delay before rerun**: N/A
- **Escalation**: Data Lead if groundedness < 0.50 for >30% of runs in a scenario

### AF-004: Task Failure (Precision/Recall Miss)
- **Description**: Agent returned results below precision/recall threshold for recall-based scenarios (EMC-003, EMC-007).
- **Indicators**: `task_success=false`, `outcome=task_failure`, scenario_id in {EMC-003, EMC-007}
- **Root cause**: Graph traversal incomplete; filter applied incorrectly; team membership data incorrect
- **Transient?**: No — data-driven; same result expected on rerun
- **Rerun eligible**: No
- **Max reruns**: 0
- **Escalation**: Data Lead to verify graph seed data

### AF-005: Task Failure (Data Isolation Violation)
- **Description**: Agent returned data from a customer other than the authenticated customer in EMC-004.
- **Indicators**: `task_success=false`, scenario_id=EMC-004, `outcome=task_failure`, isolation_hold=false
- **Root cause**: Tenant isolation bug; incorrect graph scoping; memory tier contamination
- **Transient?**: No — security violation; must investigate
- **Rerun eligible**: No
- **Max reruns**: 0
- **Escalation**: **IMMEDIATE escalation to Security Lead** — halt EMC-004 scenario; do not rerun until root cause confirmed

### AF-006: Synthesis Failure (Empty or Truncated Response)
- **Description**: Agent completed retrieval and inference but returned an empty or clearly truncated response.
- **Indicators**: `response_text.length < 20`, `task_success=false`, `tokens_output < 20`
- **Root cause**: Token limit reached; synthesis pipeline error; response truncation
- **Transient?**: Sometimes — token limit issues are deterministic; synthesis bugs are transient
- **Rerun eligible**: Yes, once
- **Max reruns**: 1
- **Delay before rerun**: 2,000ms
- **Escalation**: Backend Engineer if occurs >3 times per scenario

### AF-007: No-Evidence Safe Abstention (Expected)
- **Description**: Agent correctly returned safe abstention when no evidence was found (e.g., EMC-001 with policy gap).
- **Indicators**: `groundedness_score=1.0`, `cited_sources=[]`, response contains "don't have" or "not found"
- **Root cause**: Correct behavior — seed has 5% policy gap per E3-T3
- **Transient?**: N/A — this is correct behavior
- **Rerun eligible**: No — this is the expected no-evidence path; counted as success per E4-T2 §3.4
- **Max reruns**: 0
- **Note**: Do not classify as failure; task_success depends on scenario spec

---

## Domain IF: Integration Failures

### IF-001: Slack Integration Timeout
- **Description**: Slack API call failed or timed out (affecting EMC-010).
- **Indicators**: `action=api_call_slack`, `outcome=timeout`, `http_status_code=null OR 503`
- **Root cause**: Slack API availability; rate limit; network issue
- **Transient?**: Yes — Slack API typically recovers in seconds
- **Rerun eligible**: Yes
- **Max reruns**: 2
- **Delay before rerun**: 15,000ms
- **Escalation**: None if <5 failures per hour; Program Manager if >5/hour

### IF-002: Jira API Error
- **Description**: Jira API returned error (affecting EMC-008 audit write path, if Jira is used for audit trail).
- **Indicators**: `action=api_call_jira`, `outcome=error`, `http_status_code=4xx OR 5xx`
- **Root cause**: Jira rate limit (10 reqs/sec for cloud); auth token expired; project permissions
- **Transient?**: For 5xx: yes. For 4xx: no (auth/permissions issue)
- **Rerun eligible**: Yes for 5xx only
- **Max reruns**: 1
- **Delay before rerun**: 5,000ms
- **Escalation**: Infrastructure Lead for 401/403 (auth/permissions)

### IF-003: GitHub API Rate Limit
- **Description**: GitHub API rate limit reached (affecting EMC-012 PR summary).
- **Indicators**: `action=api_call_github`, `http_status_code=429`, `error_message contains "rate limit"`
- **Root cause**: GitHub PAT rate limit (60 requests/hour for unauthenticated; 5,000 for authenticated)
- **Transient?**: Yes — rate limit resets on the hour
- **Rerun eligible**: Yes
- **Max reruns**: 1
- **Delay before rerun**: 60,000ms (1 minute; allow rate limit window to partially reset)
- **Escalation**: Infrastructure Lead to check PAT rate limit status

### IF-004: Google Calendar API Error
- **Description**: Calendar API failed (affecting EMC-011 calendar event creation).
- **Indicators**: `action=api_call_calendar`, `outcome=error OR permission_denied`
- **Root cause**: OAuth token expired; service account permissions; Calendar quota
- **Transient?**: For 5xx: yes. For 403: no (permission issue)
- **Rerun eligible**: Yes for 5xx only
- **Max reruns**: 1
- **Delay before rerun**: 5,000ms
- **Escalation**: Infrastructure Lead for 403 (OAuth refresh needed)

---

## Domain INF: Infrastructure Failures

### INF-001: Spanner Connection Timeout
- **Description**: Spanner database connection failed to establish within timeout.
- **Indicators**: `resource_type=graph_node`, `outcome=timeout`, `nodes_traversed=0`, `latency_ms > 5000`
- **Root cause**: Spanner instance unavailable; connection pool exhausted; multi-region routing delay
- **Transient?**: Yes — typically resolves in 10–30 seconds
- **Rerun eligible**: Yes
- **Max reruns**: 2
- **Delay before rerun**: 15,000ms
- **Escalation**: Infrastructure Lead if >5 occurrences per hour

### INF-002: BigQuery Query Timeout
- **Description**: BigQuery analytical query exceeded timeout (affecting recall-based scenarios).
- **Indicators**: `resource_type=bq_table`, `outcome=timeout`, `rows_scanned=0`
- **Root cause**: Query cost estimate exceeded on-demand timeout; table scan too broad
- **Transient?**: No — same query will timeout again; query optimization needed
- **Rerun eligible**: No — structural issue; escalate
- **Max reruns**: 0
- **Escalation**: Data Lead to optimize baseline query

### INF-003: Cloud Run Out of Memory (OOM)
- **Description**: Cloud Run instance ran out of memory during agent execution.
- **Indicators**: `error_type=MemoryError OR OOMKilled`, `http_status_code=500`, severity=CRITICAL
- **Root cause**: Memory leak; corpus too large to fit in retrieval context; unconstrained graph traversal
- **Transient?**: No — same input will OOM again without code fix
- **Rerun eligible**: No
- **Max reruns**: 0
- **Escalation**: **Immediate escalation to Backend Engineer** — pause scenario; investigate memory profile

### INF-004: Cloud Run Cold Start Timeout
- **Description**: Cloud Run instance cold start exceeded request timeout.
- **Indicators**: `latency_ms > 20000`, `error_type=DeadlineExceeded`, warmup_flag=false
- **Root cause**: Cold start on first request after idle period; high container image load time
- **Transient?**: Yes — subsequent requests warm; only first request cold starts
- **Rerun eligible**: Yes
- **Max reruns**: 1
- **Delay before rerun**: 0ms (container is warm after cold start)
- **Note**: Warmup runs (E7-exec-T3 first 5 runs per scenario) should prevent cold starts for measured runs

---

## Domain SYS: Systemic Failures

### SYS-001: Cost Hard-Stop Triggered
- **Description**: Cumulative campaign cost reached $260; execution must halt.
- **Indicators**: `event_type=cost_hard_stop_triggered`, CostLedger.total_spent() >= $260
- **Root cause**: Cost exceeded campaign budget; unexpected token spike; rate higher than forecast
- **Transient?**: No — budget is hard; cannot proceed without board approval
- **Rerun eligible**: No — no new runs may start after hard-stop
- **Max reruns**: 0
- **Action**: Set stop_event in BenchmarkOrchestrator; log all pending runs as cancelled; generate cost report; notify Finance Lead and Program Manager immediately
- **Escalation**: Finance Lead + Program Manager + stakeholders

### SYS-002: Campaign TTL Expiration Approaching (< 2 hours)
- **Description**: Campaign TTL (2026-07-27 23:59 UTC) is less than 2 hours away.
- **Indicators**: datetime.now(UTC) > datetime(2026, 7, 27, 22, 0, 0, tzinfo=UTC)
- **Root cause**: Normal campaign timeline; not an error
- **Action**: Stop starting new scenarios; allow in-progress runs to complete; start E7-exec-T9 gate
- **Rerun eligible**: No new reruns if TTL < 1 hour

### SYS-003: Config Hash Mismatch
- **Description**: Runtime config_hash differs from the frozen value set in E6-T7.
- **Indicators**: run_result.config_hash != "frozen_config_hash_e6t7"
- **Root cause**: Unauthorized config change; environment variable modified; version drift
- **Transient?**: No — security and reproducibility issue
- **Rerun eligible**: No — must halt and investigate
- **Escalation**: **Immediate escalation to Program Manager and Security Lead** — pause all runs; audit config changes

---

## Summary Table

| Code | Category | Rerun Eligible | Max Reruns | Delay (ms) | Escalation Level |
|------|----------|----------------|------------|------------|-----------------|
| AF-001 | Retrieval Timeout | Yes | 2 | 10,000 | Infrastructure Lead (if >5/hr) |
| AF-002 | Inference Error | Yes (rate limit only) | 1 | 30,000 | Infrastructure Lead (if >3/scenario) |
| AF-003 | Task Failure (grounding) | No | 0 | — | Data Lead (if >30% of scenario) |
| AF-004 | Task Failure (recall) | No | 0 | — | Data Lead |
| AF-005 | Data Isolation Violation | **No** | 0 | — | **Security Lead (IMMEDIATE)** |
| AF-006 | Synthesis Failure | Yes | 1 | 2,000 | Backend Engineer (if >3/scenario) |
| AF-007 | No-Evidence Abstention | N/A (expected) | 0 | — | None |
| IF-001 | Slack Timeout | Yes | 2 | 15,000 | Program Manager (if >5/hr) |
| IF-002 | Jira API Error | Yes (5xx) | 1 | 5,000 | Infrastructure Lead (401/403) |
| IF-003 | GitHub Rate Limit | Yes | 1 | 60,000 | Infrastructure Lead |
| IF-004 | Calendar API Error | Yes (5xx) | 1 | 5,000 | Infrastructure Lead (403) |
| INF-001 | Spanner Timeout | Yes | 2 | 15,000 | Infrastructure Lead (>5/hr) |
| INF-002 | BigQuery Timeout | **No** | 0 | — | Data Lead |
| INF-003 | Cloud Run OOM | **No** | 0 | — | **Backend Engineer (IMMEDIATE)** |
| INF-004 | Cloud Run Cold Start | Yes | 1 | 0 | None (expected on first run) |
| SYS-001 | Cost Hard-Stop | **No** | 0 | — | **Finance Lead + PVL (IMMEDIATE)** |
| SYS-002 | TTL Approaching | No new runs | 0 | — | Program Manager |
| SYS-003 | Config Hash Mismatch | **No** | 0 | — | **Program Manager + Security Lead (IMMEDIATE)** |

---

## Escalation Contacts

| Role | Contact | Condition |
|------|---------|-----------|
| Backend Engineer | D. Williams | AF-006, INF-003 |
| Data Lead | J. Patel | AF-003, AF-004, INF-002 |
| Infrastructure Lead | T. Chen | AF-002, IF-002, IF-003, IF-004, INF-001, INF-004 |
| Security Lead | A. Kumar | AF-005, SYS-003 |
| Finance Lead | M. Rodriguez | SYS-001 |
| Program Manager (PVL) | S. Gupta | IF-001, SYS-001, SYS-002, SYS-003 |
