# E2-T1 — Campaign IAM Matrix

**Epic:** E2 — Security, Agent, and Integration Design Readiness
**Task:** E2-T1
**Date:** 2026-07-08
**Status:** Approved
**Owner:** Security Reviewer

---

## 1. Identity Inventory

### 1.1 Service Accounts

| Identity | SA Email | Purpose | Activation |
|----------|---------|---------|-----------|
| `amg-campaign-svc` | `amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com` | Cloud Run runtime SA — used by all agent workloads | E5-T5 |
| `amg-campaign-tf` | `amg-campaign-tf@{{PROJECT_ID}}.iam.gserviceaccount.com` | Terraform provisioning SA — infrastructure-only | E5-T5 |
| `amg-campaign-scheduler` | `amg-campaign-scheduler@{{PROJECT_ID}}.iam.gserviceaccount.com` | Cloud Scheduler job invoker | E5-T5 |

### 1.2 Human Principals (Campaign Personnel)

| Principal | Role | Access Scope |
|-----------|------|-------------|
| Platform Engineer | `roles/owner` scoped to campaign project | Full project access during setup; demoted after E5-T8 |
| MLE Lead | `roles/bigquery.dataEditor`, `roles/spanner.databaseUser` | Data access only; no IAM admin |
| Security Reviewer | `roles/iam.securityReviewer` | Read-only IAM audit; no resource write |
| Product Validation Lead | `roles/viewer` + `roles/monitoring.viewer` | Observability and cost monitoring only |

**Post-E5-T8 access hardening:** Platform Engineer elevated access is revoked after infrastructure gate. PE retains `roles/cloudrun.developer` for runtime operations only.

---

## 2. Service Account IAM Bindings

### 2.1 `amg-campaign-svc` — Runtime Service Account

| Resource | Role | Scope | Justification |
|----------|------|-------|--------------|
| Cloud Spanner `amg-campaign-db` | `roles/spanner.databaseUser` | Database-level | Read/write memory graph nodes and edges |
| BigQuery `raw_retail_public` | `roles/bigquery.dataViewer` | Dataset-level | Read-only access to raw retail data |
| BigQuery `curated_retail_campaign` | `roles/bigquery.dataViewer` | Dataset-level | Read-only access to curated data |
| BigQuery `benchmark_metrics` | `roles/bigquery.dataEditor` | Dataset-level | Write benchmark run results |
| GCS `amg-campaign-corpus-{{PROJECT_ID}}` | `roles/storage.objectViewer` | Bucket-level | Read text corpus files |
| Secret Manager `amg-campaign-slack-token` | `roles/secretmanager.secretAccessor` | Secret-level | Access Slack API token at runtime |
| Secret Manager `amg-campaign-calendar-token` | `roles/secretmanager.secretAccessor` | Secret-level | Access Google Calendar OAuth token |
| Secret Manager `amg-campaign-jira-token` | `roles/secretmanager.secretAccessor` | Secret-level | Access Jira API token |
| Secret Manager `amg-campaign-github-token` | `roles/secretmanager.secretAccessor` | Secret-level | Access GitHub API token |
| Cloud Logging | `roles/logging.logWriter` | Project-level | Write structured audit and trace logs |
| Cloud Trace | `roles/cloudtrace.agent` | Project-level | Emit distributed traces |

**Denied (explicit deny via IAM Conditions or absence of binding):**
- `roles/iam.admin` — never granted to runtime SA
- `roles/bigquery.dataEditor` on raw or curated datasets — read-only; writes go only to `benchmark_metrics`
- `roles/storage.objectAdmin` on corpus bucket — no delete or overwrite allowed
- `roles/secretmanager.admin` — runtime SA cannot create or rotate secrets
- Access to production project resources — no cross-project bindings

### 2.2 `amg-campaign-tf` — Terraform Service Account

| Resource | Role | Scope | Justification |
|----------|------|-------|--------------|
| Project | `roles/editor` | Project-level | Provision all campaign resources via Terraform |
| Project | `roles/iam.serviceAccountAdmin` | Project-level | Create and manage campaign SAs |
| Project | `roles/iam.serviceAccountKeyAdmin` | Project-level | Manage SA keys if needed |
| Budget API | `roles/billing.viewer` | Billing account | Read budget and billing data for alerts |
| Cloud Billing | `roles/billing.costsManager` | Billing account | Configure budget alerts |
| Secret Manager | `roles/secretmanager.admin` | Project-level | Create secret stubs; values injected separately |

**Denied:**
- No access to production project
- `roles/iam.admin` beyond service account management scope

### 2.3 `amg-campaign-scheduler` — Scheduler Invoker

| Resource | Role | Scope | Justification |
|----------|------|-------|--------------|
| Cloud Run `amg-campaign-svc` | `roles/run.invoker` | Service-level | Invoke scheduled benchmark and maintenance jobs |

**Denied:**
- No resource creation or modification rights
- No data access beyond invoking Cloud Run

---

## 3. Integration-Level IAM

These bindings apply when external integrations (Slack, Calendar, Jira, GitHub) authenticate to GCP or when the AMG service calls out to them.

### 3.1 Inbound (External → GCP)

| Integration | Auth Method | GCP Entry Point | Allowed Actions |
|-------------|------------|----------------|----------------|
| Slack Events API | Signing secret verification (HMAC-SHA256) | Cloud Run HTTP endpoint `/webhooks/slack` | Trigger agent via event payload; no GCP IAM role assigned |
| Google Calendar (push notifications) | OAuth 2.0 service account impersonation or domain-wide delegation | Cloud Run endpoint `/webhooks/calendar` | Receive watch notifications only |

### 3.2 Outbound (GCP → External)

| Integration | Auth Method | Secret Used | Scope Granted to AMG |
|-------------|------------|------------|---------------------|
| Slack API | Bot token (OAuth 2.0) | `amg-campaign-slack-token` | `chat:write`, `channels:read`, `users:read` |
| Google Calendar API | OAuth 2.0 access token | `amg-campaign-calendar-token` | `calendar.readonly`, `calendar.events` (create/update only for managed calendars) |
| Jira REST API | API token (Basic auth via token) | `amg-campaign-jira-token` | `read:issue`, `write:comment`, `read:project` |
| GitHub REST API | PAT or GitHub App installation token | `amg-campaign-github-token` | `repo:read`, `issues:write`, `pull_requests:read` |

---

## 4. Denied Actions Summary

The following actions are explicitly prohibited for all campaign identities unless stated otherwise:

| Category | Denied Action | Enforcement Method |
|----------|-------------|-------------------|
| Cross-project access | Any API call targeting a non-campaign project | IAM project scoping; no cross-project binding |
| IAM privilege escalation | `setIamPolicy` on project | Not granted to runtime SA or scheduler SA |
| Secret rotation | Updating secret versions | Only `amg-campaign-tf` may rotate; runtime SA is accessor only |
| Data deletion | `bigquery.tables.delete`, `storage.objects.delete` (corpus bucket) | No `dataOwner` or `objectAdmin` role on protected resources |
| Wildcard resource access | `*` in resource bindings | Prohibited; all bindings are resource-scoped |
| Production data access | Any binding to production Spanner, BigQuery, or GCS | No production project bindings |
| Unauthenticated invocation | `allUsers` or `allAuthenticatedUsers` on Cloud Run | Cloud Run requires authenticated invocation; no public endpoint |

---

## 5. IAM Conditions (Applied at E5-T5)

| Binding | Condition | Rationale |
|---------|-----------|-----------|
| PE `roles/editor` | `resource.name.startsWith("projects/{{PROJECT_ID}}")` | Prevents accidental cross-project actions |
| `amg-campaign-tf` `roles/editor` | Valid only for Terraform apply window; revoke after E5-T8 | Least-privilege during provisioning |
| All SA bindings | `resource.labels["campaign"] == "validation-2026"` (where supported) | Defense-in-depth label guard |

---

## 6. Review Sign-off

- [ ] Security Reviewer: _______________________  Date: ____________
- [ ] Platform Engineer: _______________________  Date: ____________
- [ ] Product Validation Lead: _______________________  Date: ____________
