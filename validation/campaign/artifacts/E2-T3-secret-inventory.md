# E2-T3 — Secret Inventory and Access Policy Design

**Epic:** E2 — Security, Agent, and Integration Design Readiness
**Task:** E2-T3
**Date:** 2026-07-08
**Status:** Approved
**Owner:** Security Reviewer

---

## 1. Secret Management Principles

| Principle | Rule |
|-----------|------|
| Storage | All secrets stored in Google Cloud Secret Manager. No secrets in environment variables, code, or Terraform state. |
| Injection | Secrets injected at runtime via Secret Manager API; never mounted as files in container unless required by integration SDK |
| Rotation | All integration tokens rotated before campaign Week 5; rotation documented in this register |
| Access granularity | Each secret grants access to exactly one external system; no bundled or shared credentials |
| Version pinning | Runtime always accesses the latest version; previous versions disabled after successful rotation confirmation |
| Audit | Every `secretmanager.versions.access` call is logged to Cloud Logging and the T3 audit graph |
| No hardcoded values | `terraform.tfvars` and CI variables hold only non-sensitive configuration; secrets are never in version control |

---

## 2. Secret Inventory

| Secret Name | Type | Integration | Owner | Created By | Accessed By | Rotation Frequency | Target Week |
|-------------|------|-------------|-------|-----------|------------|-------------------|------------|
| `amg-campaign-slack-token` | Slack Bot OAuth Token | Slack | PE | Terraform stub (value injected manually) | `amg-campaign-svc` (AGENT-SI, AGENT-CM, AGENT-EC) | Before Week 5 start | E5-T5 |
| `amg-campaign-calendar-token` | Google OAuth 2.0 Refresh Token | Google Calendar | PE | Terraform stub | `amg-campaign-svc` (AGENT-SI, AGENT-CM) | Before Week 5 start | E5-T5 |
| `amg-campaign-jira-token` | Jira API Token (Basic Auth) | Jira | PE | Terraform stub | `amg-campaign-svc` (AGENT-TA) | Before Week 5 start | E5-T5 |
| `amg-campaign-github-token` | GitHub Personal Access Token or App Installation Token | GitHub | PE | Terraform stub | `amg-campaign-svc` (AGENT-TA, AGENT-CA) | Before Week 5 start | E5-T5 |
| `amg-campaign-spanner-key` | **Not used** — Spanner access via Workload Identity / SA key-less | Spanner | — | — | — | N/A — key-less auth | — |
| `amg-campaign-vertexai-key` | **Not used** — Vertex AI access via Workload Identity | Vertex AI | — | — | — | N/A — key-less auth | — |

**Note on key-less auth:** Spanner and Vertex AI access is granted to `amg-campaign-svc` via IAM role bindings (Workload Identity Federation or direct SA attachment to Cloud Run). No SA JSON keys or API keys are created for these services.

---

## 3. Secret Lifecycle

### 3.1 Creation Process (E5-T5)

```
1. PE creates secret stub via Terraform:
   resource "google_secret_manager_secret" "slack_token" {
     secret_id = "amg-campaign-slack-token"
     labels    = { campaign = "validation-2026", owner = "product-team" }
     replication { auto {} }
   }

2. PE manually adds the secret version with the actual token value:
   gcloud secrets versions add amg-campaign-slack-token \
     --data-file=<(echo -n "$SLACK_BOT_TOKEN")

3. PE verifies access from runtime SA:
   gcloud secrets versions access latest \
     --secret=amg-campaign-slack-token \
     --impersonate-service-account=amg-campaign-svc@{{PROJECT_ID}}.iam.gserviceaccount.com
```

### 3.2 Rotation Process

```
1. Generate new token in source system (Slack, Google, Jira, GitHub).
2. Add new version to Secret Manager (do not delete old version yet):
   gcloud secrets versions add <secret-name> --data-file=<(echo -n "$NEW_TOKEN")
3. Deploy updated Cloud Run revision and confirm health.
4. Verify new version is being accessed (Cloud Logging audit entry).
5. Disable old secret version:
   gcloud secrets versions disable <old-version-id> --secret=<secret-name>
6. Record rotation in this document under Section 5.
```

### 3.3 Teardown Process (E8-T5)

```
1. Disable all secret versions before resource destroy:
   for secret in amg-campaign-slack-token amg-campaign-calendar-token \
                 amg-campaign-jira-token amg-campaign-github-token; do
     gcloud secrets versions list $secret --format='value(name)' | \
       xargs -I{} gcloud secrets versions disable {} --secret=$secret
   done

2. Destroy secrets via terraform destroy (campaign workspace scope).
3. Revoke integration tokens in source systems (Slack, Google, Jira, GitHub).
4. Record revocation in Section 5 rotation log.
```

---

## 4. Access Policy Model

### 4.1 Who Can Read Secrets

| Identity | Secrets Accessible | Access Method |
|----------|--------------------|--------------|
| `amg-campaign-svc` | All 4 integration tokens (listed in Section 2) | `roles/secretmanager.secretAccessor` at secret resource level |
| `amg-campaign-tf` | All secrets (for version management only) | `roles/secretmanager.admin` at project level |
| Campaign PE (human) | All secrets (break-glass only) | `roles/secretmanager.admin` — access logged and reviewed |
| MLE Lead | None | No Secret Manager bindings |
| Security Reviewer | Metadata only (no version access) | `roles/secretmanager.viewer` — cannot access payload |

### 4.2 Who Can Write / Rotate Secrets

| Identity | Can Create Secret | Can Add Version | Can Disable Version |
|----------|-----------------|----------------|-------------------|
| `amg-campaign-tf` | ✅ (via Terraform) | ✅ | ✅ |
| Campaign PE | ✅ (manual only, documented) | ✅ | ✅ |
| `amg-campaign-svc` | ❌ | ❌ | ❌ |
| All others | ❌ | ❌ | ❌ |

### 4.3 Secret Access Audit Policy

- Every access to a secret version generates a Cloud Logging entry under `cloudaudit.googleapis.com/data_access`.
- Secret access events are also written to the T3 Audit graph by the AMG runtime with `event_type=SECRET_ACCESS`.
- Security Reviewer reviews Cloud Logging audit entries for all secret accesses at the Week 4 gate (E5-T8) and again before benchmark execution begins (E6-T7).

---

## 5. Rotation Log

| Secret | Old Version Disabled | New Version Added | Rotated By | Rotation Date | Notes |
|--------|---------------------|------------------|-----------|--------------|-------|
| _(all empty — no rotations yet)_ | — | — | — | — | — |

---

## 6. Credential Ownership Matrix

| Credential | Owned By | Managed By | Emergency Contact |
|-----------|---------|-----------|-----------------|
| Slack Bot Token | Platform Engineer | PE | PVL |
| Google Calendar OAuth Token | Platform Engineer | PE | PVL |
| Jira API Token | Platform Engineer | PE | PVL |
| GitHub PAT / App Token | Platform Engineer | PE (or repo owner) | PVL |

---

## 7. Compliance Checks (Verified at E5-T5 and E6-T7)

- [ ] No secrets stored in environment variables on Cloud Run service
- [ ] No SA JSON keys created for Spanner or Vertex AI
- [ ] All secret stubs have campaign labels (`campaign=validation-2026`)
- [ ] `amg-campaign-svc` has `secretAccessor` only (not `admin` or `editor`) on Secret Manager
- [ ] All secret accesses appear in Cloud Audit Logs
- [ ] Rotation plan documented and scheduled before Week 5
- [ ] No integration tokens committed to any version control system

---

## 8. Review Sign-off

- [ ] Security Reviewer: _______________________  Date: ____________
- [ ] Platform Engineer: _______________________  Date: ____________
