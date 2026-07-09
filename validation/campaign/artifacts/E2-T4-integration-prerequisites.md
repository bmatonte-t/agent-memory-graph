# E2-T4 — Mandatory Integration Prerequisite Catalog

**Epic:** E2 — Security, Agent, and Integration Design Readiness
**Task:** E2-T4
**Date:** 2026-07-08
**Status:** Approved
**Owner:** Platform Engineer

---

## Integration Summary

| Integration | Type | Agents Using | Mandatory | Setup Owner | Setup Week |
|-------------|------|-------------|----------|------------|-----------|
| Slack | Bot OAuth 2.0 | AGENT-SI, AGENT-CM, AGENT-EC | Yes | PE | E5-T5 / E6-T5 |
| Google Calendar | OAuth 2.0 | AGENT-SI, AGENT-CM | Yes | PE | E5-T5 / E6-T5 |
| Jira | API Token | AGENT-TA | Yes | PE | E5-T5 / E6-T5 |
| GitHub | PAT or App Token | AGENT-TA, AGENT-CA | Yes | PE | E5-T5 / E6-T5 |

---

## Integration 1: Slack

### Overview

The AMG runtime connects to Slack as a **Slack Bot** using OAuth 2.0. The bot receives events via the Events API (inbound webhooks) and posts messages using the Web API (outbound calls).

### Prerequisite Steps

| # | Step | Owner | Blocker | Notes |
|---|------|-------|---------|-------|
| 1 | Create a Slack App in the target workspace | PE | None | App name: `amg-campaign-bot`; Slack workspace must be the campaign test workspace |
| 2 | Enable Bot Token Scopes | PE | Step 1 | Required scopes: `chat:write`, `channels:read`, `channels:history` (read only for event context), `users:read` |
| 3 | Enable Events API and set Request URL | PE | Cloud Run service deployed (E5-T7) | URL: `https://<amg-campaign-svc-url>/webhooks/slack`; must use HTTPS |
| 4 | Subscribe to Bot Events | PE | Step 3 | Subscribe to: `message.channels` (bot-addressed only), `app_mention` |
| 5 | Install app to workspace and capture Bot Token | PE | Step 2 | Token stored in `amg-campaign-slack-token` secret (E5-T5) |
| 6 | Add bot to designated campaign test channels | PE | Step 5 | Channels: `#campaign-test-ec`, `#campaign-test-si`, `#campaign-alerts` |
| 7 | Verify signing secret is stored and used for HMAC verification | SR | Step 5 | Signing secret stored separately; verified in webhook handler before processing |

### Required OAuth Scopes

| Scope | Permission | Used By |
|-------|-----------|---------|
| `chat:write` | Post messages in channels where bot is a member | AGENT-SI, AGENT-EC, AGENT-CM |
| `channels:read` | List public channels | AGENT-SI |
| `users:read` | Look up user profiles by ID | AGENT-SI, AGENT-EC |
| `channels:history` | Read recent messages in channels (limited to bot mention context only) | AGENT-SI |

**Explicitly excluded:** `chat:write.public` (no posting to channels where bot is not a member), `files:read`, `dms:read`, `admin.*`

### Smoke Test Checklist (E6-T6)

- [ ] Bot can post a test message to `#campaign-alerts`
- [ ] Bot receives and acknowledges an `app_mention` event
- [ ] Signing secret HMAC verification rejects malformed request
- [ ] Token scope boundary: bot cannot read DMs

---

## Integration 2: Google Calendar

### Overview

The AMG runtime uses the Google Calendar API with an OAuth 2.0 refresh token to manage events on designated campaign calendars. **Domain-wide delegation is not used.** The token is scoped to a specific campaign service account's calendar.

### Prerequisite Steps

| # | Step | Owner | Blocker | Notes |
|---|------|-------|---------|-------|
| 1 | Create OAuth 2.0 credentials in the GCP project | PE | `{{PROJECT_ID}}` resolved (E5-T1) | Credential type: Web application or Desktop (for initial token generation) |
| 2 | Configure OAuth Consent Screen | PE | Step 1 | App name: `AMG Campaign Bot`; scopes limited to calendar only; internal (not public) |
| 3 | Generate OAuth 2.0 refresh token via consent flow | PE | Step 2 | Scope: `https://www.googleapis.com/auth/calendar` scoped to campaign calendar resource only |
| 4 | Store refresh token in Secret Manager | PE | E5-T5 | Stored as `amg-campaign-calendar-token` |
| 5 | Create dedicated campaign calendar resource | PE | Step 2 | Calendar name: `AMG Campaign Scheduling`; shared only with campaign team |
| 6 | Verify token can read and create events on designated calendar | PE | Step 4 | Test via `calendars.get` and `events.insert` API calls |
| 7 | Confirm token does NOT have access to personal calendars | SR | Step 6 | Test `calendars.list` returns only campaign calendar |

### Required OAuth Scopes

| Scope | Permission | Used By |
|-------|-----------|---------|
| `https://www.googleapis.com/auth/calendar` | Full access to campaign calendar resource | AGENT-SI, AGENT-CM |

**Note:** The narrower scope `calendar.readonly` is insufficient because event creation is required. The token's effective permission is constrained by the calendar ACL (shared with campaign calendar only).

### Smoke Test Checklist (E6-T6)

- [ ] Agent can list events on `AMG Campaign Scheduling` calendar
- [ ] Agent can create a test event
- [ ] Agent cannot list or access events on personal calendars
- [ ] Refresh token successfully exchanges for access token

---

## Integration 3: Jira

### Overview

The AMG runtime authenticates to Jira using an **API token** with HTTP Basic Auth (username + token). The token is scoped to a campaign Jira project.

### Prerequisite Steps

| # | Step | Owner | Blocker | Notes |
|---|------|-------|---------|-------|
| 1 | Identify or create a campaign Jira project | PE | Access to Jira workspace | Project key: `AMGC` (AMG Campaign); project type: Software or Service Management |
| 2 | Create a campaign service user account in Jira | PE | Step 1 | User: `amg-campaign-bot@<org-domain>`; do not use a personal account |
| 3 | Generate API token for the service user | PE | Step 2 | From Atlassian account settings; token stored as `amg-campaign-jira-token` |
| 4 | Assign service user to campaign project with required permissions | PE | Step 2 | Required: `BROWSE_PROJECTS`, `CREATE_ISSUES`, `ADD_COMMENTS`, `TRANSITION_ISSUES` |
| 5 | Store API token in Secret Manager | PE | E5-T5 | Format: Base64(`service-user-email:api-token`) or raw token depending on auth method |
| 6 | Verify token can create an issue and add a comment in `AMGC` | PE | Step 5 | Use Jira REST API v3 `/rest/api/3/issue` |
| 7 | Confirm token cannot access other projects | SR | Step 6 | Test `GET /rest/api/3/project` — should return only `AMGC` |

### Required Jira Permissions (Campaign Project Only)

| Permission | Operations | Used By |
|-----------|-----------|---------|
| `BROWSE_PROJECTS` | Read issues and project metadata | AGENT-TA |
| `CREATE_ISSUES` | Create new issues | AGENT-TA |
| `ADD_COMMENTS` | Add comments to existing issues | AGENT-TA |
| `TRANSITION_ISSUES` | Move issues through workflow transitions | AGENT-TA |

**Explicitly excluded:** `DELETE_ISSUES`, `ADMINISTER_PROJECTS`, `MANAGE_SPRINTS_PERMISSION`, access to non-campaign projects.

### Smoke Test Checklist (E6-T6)

- [ ] Agent can read issues from project `AMGC`
- [ ] Agent can create a test issue
- [ ] Agent can add a comment to an issue
- [ ] Agent cannot access issues outside `AMGC`
- [ ] API token auth returns HTTP 200 (not 401 or 403)

---

## Integration 4: GitHub

### Overview

The AMG runtime authenticates to GitHub using a **Personal Access Token (PAT)** or a **GitHub App installation token**. The token is scoped to the campaign repository only.

**Preferred:** GitHub App installation token (more granular permissions, auditable, expirable). PAT is acceptable for campaign scope if App setup is blocked.

### Prerequisite Steps

#### Option A: GitHub App (Preferred)

| # | Step | Owner | Blocker | Notes |
|---|------|-------|---------|-------|
| 1 | Create a GitHub App in the organization | PE | GitHub org admin access | App name: `amg-campaign-bot`; homepage: campaign repo URL |
| 2 | Configure permissions | PE | Step 1 | Repository: `Issues: Read/Write`, `Pull requests: Read`, `Contents: Read`; no admin permissions |
| 3 | Install app on campaign repository only | PE | Step 2 | Scope installation to the single campaign repository |
| 4 | Generate private key and installation ID | PE | Step 3 | Private key stored as `amg-campaign-github-token` in Secret Manager |
| 5 | Configure runtime to use JWT → installation token exchange | PE | Step 4 | Token expires after 1 hour; runtime must refresh automatically |
| 6 | Verify installation token can read issues and create a comment | PE | Step 5 | Test on `agent-memory-graph` repo |

#### Option B: PAT (Fallback)

| # | Step | Owner | Blocker | Notes |
|---|------|-------|---------|-------|
| 1 | Create a GitHub machine user account | PE | GitHub org admin | User: `amg-campaign-bot`; do not use personal accounts |
| 2 | Generate PAT with fine-grained permissions | PE | Step 1 | Scope to campaign repository only; permissions: `issues:write`, `pull_requests:read`, `contents:read` |
| 3 | Store PAT in Secret Manager | PE | E5-T5 | Stored as `amg-campaign-github-token` |
| 4 | Verify PAT can read issues and create a comment | PE | Step 3 | |
| 5 | Confirm PAT cannot access other repositories | SR | Step 4 | Fine-grained PATs support single-repo scope |

### Required GitHub Permissions (Campaign Repository Only)

| Permission | Level | Operations | Used By |
|-----------|-------|-----------|---------|
| `Issues` | Read/Write | Read issues, create issues, add comments | AGENT-TA, AGENT-CA |
| `Pull requests` | Read | Summarize PR content and diffs | AGENT-CA |
| `Contents` | Read | Read repository file contents for context | AGENT-CA |

**Explicitly excluded:** `Administration`, `Secrets`, `Environments`, `Actions`, push/merge/delete on any branch, access to other repositories.

### Smoke Test Checklist (E6-T6)

- [ ] Agent can list open issues on campaign repository
- [ ] Agent can create a test issue
- [ ] Agent can read a pull request diff
- [ ] Agent cannot push code or create branches
- [ ] Agent cannot access other repositories in the organization
- [ ] Token refreshes correctly (for GitHub App installation tokens)

---

## Pre-requisite Completion Tracker

This table is filled in at E6-T5. All rows must be checked before benchmark execution begins (E6-T7 freeze).

| Integration | Setup Complete | Smoke Passed | Frozen Version | Notes |
|-------------|---------------|-------------|---------------|-------|
| Slack | ☐ | ☐ | — | |
| Google Calendar | ☐ | ☐ | — | |
| Jira | ☐ | ☐ | — | |
| GitHub | ☐ | ☐ | — | |

---

## Integration Failure Taxonomy (Reference for E6-T6)

| Failure Code | Meaning | Response |
|-------------|---------|---------|
| `INTEGRATION_AUTH_FAILURE` | Token expired, revoked, or invalid | Refresh token; if fails, escalate to PE |
| `INTEGRATION_RATE_LIMITED` | API rate limit hit | Backoff per integration API docs; do not retry burst |
| `INTEGRATION_SCOPE_DENIED` | Action outside granted scope | Log `AUTHORIZATION_DENIED` to T3; return error to caller |
| `INTEGRATION_UNAVAILABLE` | Integration API unreachable | Return degraded-mode response; log to T3 |
| `INTEGRATION_TIMEOUT` | No response within timeout window | Retry once; if fails, return `INTEGRATION_TIMEOUT` |
