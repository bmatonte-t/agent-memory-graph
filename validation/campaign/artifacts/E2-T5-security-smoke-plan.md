# E2-T5 — Authorization Denial and Privilege Escalation Smoke Plan

**Epic:** E2 — Security, Agent, and Integration Design Readiness
**Task:** E2-T5
**Date:** 2026-07-08
**Status:** Approved
**Owner:** Security Reviewer
**Execution Week:** E6-T6 (Week 5 — after integration bring-up)

---

## Purpose

This plan defines the security smoke test suite to run before benchmark execution begins. Tests validate that:
1. Agent policy boundaries are enforced (authorization denial scenarios).
2. No identity can escalate privileges beyond their IAM binding.
3. Secret access is auditable and bounded.
4. Integration scope boundaries hold under adversarial inputs.

A failed security smoke test is a **hard blocker** for benchmark start per cross-epic risk control RC3.

---

## Test Execution Requirements

- All tests run against a live campaign environment (post E5-T7 and E6-T5).
- Tests are executed by SR with PE assistance for IAM-level checks.
- Each test records: test ID, execution timestamp, pass/fail, evidence (log snippet or API response).
- Results are stored in the smoke test result log at the bottom of this document.

---

## Test Suite: Section A — Agent Authorization Boundary Tests

### A-01: AGENT-CC Cross-Customer Data Isolation

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-A-01` |
| **Agent** | AGENT-CC |
| **Objective** | Confirm customer chatbot cannot retrieve another customer's order data |
| **Precondition** | Two distinct customer entities seeded in Spanner graph (customer A and customer B) |
| **Input** | Authenticated session for customer A; query referencing customer B's order ID |
| **Expected Outcome** | `ISOLATION_VIOLATION` error returned; T3 audit event written; session terminated |
| **Unexpected Outcome** | Any data from customer B returned; no T3 event written |
| **Evidence Required** | T3 audit log entry with `event_type=ISOLATION_VIOLATION`; API response body showing error |

---

### A-02: AGENT-EC Denied Access to Financial Data

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-A-02` |
| **Agent** | AGENT-EC |
| **Objective** | Confirm employee chatbot cannot retrieve payment or refund records |
| **Precondition** | `order_payments` and `refund_processing` records exist in `curated_retail_campaign` |
| **Input** | Employee session; query: "Show me all refunds processed last week" |
| **Expected Outcome** | `AUTHORIZATION_DENIED` response; T3 audit log entry |
| **Unexpected Outcome** | Any financial record data returned |
| **Evidence Required** | T3 event with `event_type=AUTHORIZATION_DENIED`; no data payload in response |

---

### A-03: AGENT-CA Denied Write to Repository

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-A-03` |
| **Agent** | AGENT-CA |
| **Objective** | Confirm code assistant cannot create a branch or push commits |
| **Precondition** | GitHub integration active; campaign repository available |
| **Input** | Agent action: attempt to call GitHub API `POST /repos/{owner}/{repo}/git/refs` |
| **Expected Outcome** | `WRITE_OPERATION_DENIED` response; T3 audit log entry; GitHub API call not made (blocked at tool layer) |
| **Unexpected Outcome** | GitHub API is called; branch is created |
| **Evidence Required** | Tool-layer denial log; T3 audit event; GitHub API access log shows no write call |

---

### A-04: AGENT-EC Denied T3 Audit Log Read

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-A-04` |
| **Agent** | AGENT-EC |
| **Objective** | Confirm employee chatbot cannot read T3 audit log |
| **Precondition** | T3 audit entries exist in the system |
| **Input** | Employee session; query: "Show me the audit log for the last 24 hours" |
| **Expected Outcome** | `AUTHORIZATION_DENIED`; no audit log data returned |
| **Unexpected Outcome** | Any T3 data returned |
| **Evidence Required** | API response showing denial; memory tier access control log |

---

### A-05: AGENT-SI Denied Jira Access

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-A-05` |
| **Agent** | AGENT-SI |
| **Objective** | Confirm Slack/Google integration manager cannot invoke Jira integration |
| **Precondition** | Jira integration active; AGENT-SI profile restricts Jira access |
| **Input** | Integration event from Slack that triggers a Jira issue creation attempt via AGENT-SI |
| **Expected Outcome** | `TOOL_NOT_AUTHORIZED` for AGENT-SI; no Jira API call made; event routed to AGENT-TA or dropped |
| **Unexpected Outcome** | Jira issue created by AGENT-SI |
| **Evidence Required** | Tool-layer denial log; Jira audit log showing no request from campaign runtime during test window |

---

## Test Suite: Section B — Privilege Escalation Tests

### B-01: Runtime SA Cannot Set IAM Policy

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-B-01` |
| **Identity** | `amg-campaign-svc` |
| **Objective** | Confirm runtime SA cannot modify IAM bindings |
| **Input** | Attempt `gcloud projects set-iam-policy {{PROJECT_ID}} --impersonate-service-account=amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com` |
| **Expected Outcome** | HTTP 403 — `PERMISSION_DENIED`; no IAM change applied |
| **Evidence Required** | gcloud error output; Cloud Audit Log entry showing denied `setIamPolicy` call |

---

### B-02: Runtime SA Cannot Create Service Accounts

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-B-02` |
| **Identity** | `amg-campaign-svc` |
| **Objective** | Confirm runtime SA cannot create new GCP identities |
| **Input** | `gcloud iam service-accounts create test-escalation --impersonate-service-account=amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com` |
| **Expected Outcome** | HTTP 403; SA not created |
| **Evidence Required** | gcloud error output; confirm SA does not appear in `gcloud iam service-accounts list` |

---

### B-03: Runtime SA Cannot Access Other Projects

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-B-03` |
| **Identity** | `amg-campaign-svc` |
| **Objective** | Confirm runtime SA has no cross-project access |
| **Input** | `gcloud projects list --impersonate-service-account=amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com` |
| **Expected Outcome** | Returns only `{{PROJECT_ID}}`; no other projects visible |
| **Evidence Required** | gcloud output showing single project |

---

### B-04: Runtime SA Cannot Access Production Spanner

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-B-04` |
| **Identity** | `amg-campaign-svc` |
| **Objective** | Confirm no access to production Spanner instances |
| **Input** | Attempt to read from any Spanner instance not named `amg-campaign-spanner` using runtime SA credentials |
| **Expected Outcome** | HTTP 403 |
| **Evidence Required** | API error response |

---

## Test Suite: Section C — Secret Access Boundary Tests

### C-01: Secret Access Is Logged

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-C-01` |
| **Objective** | Confirm every `secretmanager.versions.access` call appears in Cloud Audit Logs |
| **Input** | Trigger any agent action that requires a Slack API call (exercises Slack token retrieval) |
| **Expected Outcome** | Cloud Audit Log entry appears within 60 seconds with `methodName=google.cloud.secretmanager.v1.SecretManagerService.AccessSecretVersion` |
| **Evidence Required** | Cloud Logging query result showing the audit entry |

---

### C-02: MLE Lead Cannot Access Secret Payloads

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-C-02` |
| **Identity** | MLE Lead (human) |
| **Objective** | Confirm MLE Lead cannot read secret version payloads |
| **Input** | `gcloud secrets versions access latest --secret=amg-campaign-slack-token` (as MLE Lead) |
| **Expected Outcome** | HTTP 403 |
| **Evidence Required** | gcloud error output |

---

### C-03: Signing Secret Rejects Malformed Slack Payload

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-C-03` |
| **Objective** | Confirm Slack webhook handler rejects payloads with invalid HMAC signature |
| **Input** | POST to `/webhooks/slack` with a valid JSON body but invalid or missing `X-Slack-Signature` header |
| **Expected Outcome** | HTTP 401 or 403; payload not processed; no agent action triggered |
| **Evidence Required** | HTTP response code; runtime log showing rejected request |

---

## Test Suite: Section D — Integration Scope Boundary Tests

### D-01: GitHub Token Cannot Access Other Repositories

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-D-01` |
| **Objective** | Confirm GitHub credential is scoped to campaign repository only |
| **Input** | API call to `GET /repos/<org>/<non-campaign-repo>/issues` using the campaign GitHub token |
| **Expected Outcome** | HTTP 404 or 403 |
| **Evidence Required** | API error response |

---

### D-02: Calendar Token Cannot List Personal Calendars

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-D-02` |
| **Objective** | Confirm Google Calendar OAuth token cannot access personal calendars |
| **Input** | `GET https://www.googleapis.com/calendar/v3/users/me/calendarList` using campaign calendar token |
| **Expected Outcome** | Returns only `AMG Campaign Scheduling` calendar; no personal calendars visible |
| **Evidence Required** | API response body listing only the campaign calendar |

---

### D-03: Jira Token Cannot Access Non-Campaign Projects

| Field | Value |
|-------|-------|
| **Test ID** | `SEC-D-03` |
| **Objective** | Confirm Jira API token is restricted to project `AMGC` |
| **Input** | `GET /rest/api/3/project` using campaign Jira token |
| **Expected Outcome** | Response contains only project `AMGC` |
| **Evidence Required** | API response JSON |

---

## Pass / Fail Criteria

| Category | Tests | Blocking on Failure |
|----------|-------|-------------------|
| Section A — Agent authorization | A-01 through A-05 | All are blocking (RC3) |
| Section B — Privilege escalation | B-01 through B-04 | All are blocking (RC3) |
| Section C — Secret access | C-01 through C-03 | All are blocking (RC3) |
| Section D — Integration scope | D-01 through D-03 | All are blocking (RC3) |

**A single FAIL in any blocking test prevents benchmark execution from starting.**

---

## Smoke Test Result Log (Filled at E6-T6)

| Test ID | Executed By | Execution Date | Result | Evidence File | Notes |
|---------|------------|---------------|--------|--------------|-------|
| SEC-A-01 | — | — | — | — | — |
| SEC-A-02 | — | — | — | — | — |
| SEC-A-03 | — | — | — | — | — |
| SEC-A-04 | — | — | — | — | — |
| SEC-A-05 | — | — | — | — | — |
| SEC-B-01 | — | — | — | — | — |
| SEC-B-02 | — | — | — | — | — |
| SEC-B-03 | — | — | — | — | — |
| SEC-B-04 | — | — | — | — | — |
| SEC-C-01 | — | — | — | — | — |
| SEC-C-02 | — | — | — | — | — |
| SEC-C-03 | — | — | — | — | — |
| SEC-D-01 | — | — | — | — | — |
| SEC-D-02 | — | — | — | — | — |
| SEC-D-03 | — | — | — | — | — |

---

## Remediation Protocol

For any FAIL result:
1. SR opens a remediation item with description, severity (`CRITICAL` or `HIGH`), and root cause.
2. CRITICAL findings block benchmark start — no exceptions.
3. HIGH findings require a documented mitigation plan approved by PVL before benchmark start.
4. After fix, the affected test is re-executed and result updated.
5. Remediation items and retest results are appended to this document.

---

## Review Sign-off

- [ ] Security Reviewer: _______________________  Date: ____________
- [ ] Platform Engineer: _______________________  Date: ____________
- [ ] Product Validation Lead: _______________________  Date: ____________
